"""
Single-endpoint service that aggregates every piece of data needed
for the candidate dashboard in one database round-trip set.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.candidate_profile_model import CandidateProfile
from src.models.job_application_model import JobApplication, ApplicationStatus
from src.models.job_model import Job
from src.models.resume_model import Resume
from src.models.skill_gap_report_model import SkillGapReport
from src.models.user_model import User, UserRole
from src.models.recruiter_model import RecruiterProfile
from src.schema.candidate_dashboard_schema import (
    CandidateDashboardResponse,
    CandidateKPI,
    StatusBreakdownItem,
    WeeklyApplicationItem,
    ScoreRangeItem,
    MatchTrendItem,
    TopMissingSkillItem,
    RecentApplicationItem,
)
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


# ✅ helper for cross-platform date formatting
def format_day(dt: datetime) -> str:
    return dt.strftime("%d %b").lstrip("0")


async def get_candidate_dashboard_service(
    db: AsyncSession,
    current_user: User,
) -> CandidateDashboardResponse:

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN,
                           "Only candidates can access this dashboard")

    candidate: CandidateProfile | None = getattr(
        current_user, "candidate_profile", None)
    if candidate is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND,
                           "Candidate profile not found")

    # ── 1. Resumes ─────────────────────────────────────────────
    resume_result = await db.execute(
        select(Resume).where(Resume.candidate_id == candidate.id)
    )
    resumes = list(resume_result.scalars().all())

    # ── 2. Applications ────────────────────────────────────────
    app_result = await db.execute(
        select(JobApplication)
        .where(JobApplication.candidate_id == candidate.id)
        .order_by(JobApplication.applied_at.desc())
    )
    applications = list(app_result.scalars().all())

    # ── 3. Recent applications ─────────────────────────────────
    recent_items: list[RecentApplicationItem] = []

    for app in applications[:5]:
        job_res = await db.execute(select(Job).where(Job.id == app.job_id))
        job = job_res.scalar_one_or_none()

        company_name = None
        if job:
            rec_res = await db.execute(
                select(RecruiterProfile).where(
                    RecruiterProfile.id == job.recruiter_id)
            )
            rec = rec_res.scalar_one_or_none()
            company_name = rec.company_name if rec else None

        recent_items.append(
            RecentApplicationItem(
                id=str(app.id),
                job_title=job.title if job else "Unknown Position",
                company_name=company_name,
                status=app.status.value,
                ai_score=app.ai_score,
                applied_at=app.applied_at,
            )
        )

    # ── 4. Status breakdown ────────────────────────────────────
    status_counts = {s.value: 0 for s in ApplicationStatus}
    for app in applications:
        status_counts[app.status.value] += 1

    status_breakdown = [
        StatusBreakdownItem(status=s, count=c)
        for s, c in status_counts.items()
    ]

    # ── 5. Weekly applications ─────────────────────────────────
    now = datetime.now(timezone.utc)
    weekly_map = {}

    for week_offset in range(7, -1, -1):
        week_start = now - timedelta(weeks=week_offset + 1)
        week_end = now - timedelta(weeks=week_offset)

        label = format_day(week_start)  # ✅ fixed here

        count = sum(
            1 for a in applications
            if week_start <= _ensure_tz(a.applied_at) < week_end
        )

        weekly_map[label] = count

    weekly_applications = [
        WeeklyApplicationItem(week=w, count=c)
        for w, c in weekly_map.items()
    ]

    # ── 6. AI score distribution ───────────────────────────────
    scored = [a for a in applications if a.ai_score is not None]

    buckets = {"0–25": 0, "26–50": 0, "51–75": 0, "76–100": 0}

    for a in scored:
        s = a.ai_score
        if s <= 25:
            buckets["0–25"] += 1
        elif s <= 50:
            buckets["26–50"] += 1
        elif s <= 75:
            buckets["51–75"] += 1
        else:
            buckets["76–100"] += 1

    score_distribution = [
        ScoreRangeItem(range=r, count=c) for r, c in buckets.items()
    ]

    avg_ai_score = None
    if scored:
        avg_ai_score = round(sum(a.ai_score for a in scored) / len(scored), 1)

    # ── 7. Skill gap reports ───────────────────────────────────
    sgr_result = await db.execute(
        select(SkillGapReport)
        .where(SkillGapReport.candidate_id == candidate.id)
        .order_by(SkillGapReport.created_at.asc())
    )
    reports = list(sgr_result.scalars().all())

    avg_match = None
    if reports:
        avg_match = round(
            sum(r.match_percentage for r in reports) / len(reports), 1)

    match_trend = [
        MatchTrendItem(
            label=format_day(r.created_at),  # ✅ fixed here
            match_pct=round(r.match_percentage, 1),
        )
        for r in reports[-10:]
    ]

    # ── 8. Top missing skills ──────────────────────────────────
    missing_counter = Counter()

    for r in reports:
        for skill in (r.missing_skills or []):
            name = skill.get("name") if isinstance(skill, dict) else str(skill)
            if name:
                missing_counter[name] += 1

    top_missing = [
        TopMissingSkillItem(skill=s, count=c)
        for s, c in missing_counter.most_common(8)
    ]

    # ── 9. KPIs ────────────────────────────────────────────────
    kpi = CandidateKPI(
        total_applications=len(applications),
        pending=status_counts.get("PENDING", 0),
        shortlisted=status_counts.get("REVIEWING", 0),
        accepted=status_counts.get("ACCEPTED", 0),
        rejected=status_counts.get("REJECTED", 0),
        total_resumes=len(resumes),
        total_skill_gap_reports=len(reports),
        avg_ai_score=avg_ai_score,
        avg_match_percentage=avg_match,
        profile_score=candidate.profile_score,
    )

    # ── 10. Skills ─────────────────────────────────────────────
    raw_skills = candidate.skills or []
    skill_names = []

    for s in raw_skills:
        if isinstance(s, dict):
            skill_names.append(s.get("name", str(s)))
        else:
            skill_names.append(str(s))

    return CandidateDashboardResponse(
        full_name=candidate.full_name,
        current_role=candidate.current_role,
        location=candidate.location,
        profile_score=candidate.profile_score,
        skills=skill_names[:12],
        kpi=kpi,
        status_breakdown=status_breakdown,
        weekly_applications=weekly_applications,
        score_distribution=score_distribution,
        match_trend=match_trend,
        top_missing_skills=top_missing,
        recent_applications=recent_items,
    )


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
