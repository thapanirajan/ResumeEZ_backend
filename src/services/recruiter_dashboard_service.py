from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.external_application_model import (
    ExternalApplication,
    ExternalApplicationSource,
    ExternalApplicationStatus,
)
from src.models.job_application_model import JobApplication, ApplicationStatus
from src.models.job_model import Job
from src.models.recruiter_model import RecruiterProfile
from src.models.user_model import User, UserRole
from src.schema.recruiter_dashboard_schema import (
    ApplicationSourceItem,
    ApplicationStatusItem,
    DashboardSummary,
    JobStatusItem,
    MonthlyApplicationItem,
    RecruiterDashboardResponse,
    TopJobItem,
)
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


async def get_recruiter_dashboard_data(
    db: AsyncSession,
    current_user: User,
) -> RecruiterDashboardResponse:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "Only recruiters can access this dashboard")

    # Try eagerly-loaded relationship first, fall back to a direct DB query
    profile = getattr(current_user, "recruiter_profile", None)
    if profile is None:
        result = await db.execute(
            select(RecruiterProfile).where(RecruiterProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
    if profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Recruiter profile not found")

    recruiter_id = profile.id

    # Subquery for all job IDs owned by this recruiter — used with .in_()
    job_ids_subquery = select(Job.id).where(Job.recruiter_id == recruiter_id)

    # ── SUMMARY STATS ──────────────────────────────────────────────────────

    total_jobs_result = await db.execute(
        select(func.count(Job.id)).where(Job.recruiter_id == recruiter_id)
    )
    total_jobs = total_jobs_result.scalar() or 0

    platform_total_result = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.job_id.in_(job_ids_subquery)
        )
    )
    platform_total = platform_total_result.scalar() or 0

    external_total_result = await db.execute(
        select(func.count(ExternalApplication.id)).where(
            ExternalApplication.job_id.in_(job_ids_subquery)
        )
    )
    external_total = external_total_result.scalar() or 0

    platform_accepted_result = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.job_id.in_(job_ids_subquery),
            JobApplication.status == ApplicationStatus.ACCEPTED,
        )
    )
    platform_accepted = platform_accepted_result.scalar() or 0

    external_accepted_result = await db.execute(
        select(func.count(ExternalApplication.id)).where(
            ExternalApplication.job_id.in_(job_ids_subquery),
            ExternalApplication.status == ExternalApplicationStatus.ACCEPTED,
        )
    )
    external_accepted = external_accepted_result.scalar() or 0

    platform_pending_result = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.job_id.in_(job_ids_subquery),
            JobApplication.status == ApplicationStatus.PENDING,
        )
    )
    platform_pending = platform_pending_result.scalar() or 0

    external_pending_result = await db.execute(
        select(func.count(ExternalApplication.id)).where(
            ExternalApplication.job_id.in_(job_ids_subquery),
            ExternalApplication.status == ExternalApplicationStatus.PENDING,
        )
    )
    external_pending = external_pending_result.scalar() or 0

    summary = DashboardSummary(
        total_jobs=total_jobs,
        total_applications=platform_total + external_total,
        accepted_count=platform_accepted + external_accepted,
        pending_count=platform_pending + external_pending,
    )

    # ── APPLICATION STATUS BREAKDOWN ──────────────────────────────────────

    platform_status_rows = (
        await db.execute(
            select(JobApplication.status, func.count(JobApplication.id))
            .where(JobApplication.job_id.in_(job_ids_subquery))
            .group_by(JobApplication.status)
        )
    ).all()

    external_status_rows = (
        await db.execute(
            select(ExternalApplication.status, func.count(ExternalApplication.id))
            .where(ExternalApplication.job_id.in_(job_ids_subquery))
            .group_by(ExternalApplication.status)
        )
    ).all()

    status_counts: dict[str, int] = {}
    for status_enum, count in platform_status_rows:
        status_counts[status_enum.value] = status_counts.get(status_enum.value, 0) + count
    for status_enum, count in external_status_rows:
        status_counts[status_enum.value] = status_counts.get(status_enum.value, 0) + count

    status_order = ["PENDING", "REVIEWING", "ACCEPTED", "REJECTED"]
    application_status_breakdown = [
        ApplicationStatusItem(status=s, count=status_counts.get(s, 0))
        for s in status_order
    ]

    # ── TOP 5 JOBS BY APPLICATIONS NUMBER ────────────────────────────────────────

    platform_job_counts_rows = (
        await db.execute(
            select(JobApplication.job_id, func.count(JobApplication.id).label("cnt"))
            .where(JobApplication.job_id.in_(job_ids_subquery))
            .group_by(JobApplication.job_id)
        )
    ).all()

    external_job_counts_rows = (
        await db.execute(
            select(ExternalApplication.job_id, func.count(ExternalApplication.id).label("cnt"))
            .where(ExternalApplication.job_id.in_(job_ids_subquery))
            .group_by(ExternalApplication.job_id)
        )
    ).all()

    job_app_counts: dict = {}
    for job_id, cnt in platform_job_counts_rows:
        job_app_counts[job_id] = job_app_counts.get(job_id, 0) + cnt
    for job_id, cnt in external_job_counts_rows:
        job_app_counts[job_id] = job_app_counts.get(job_id, 0) + cnt

    top5_ids = sorted(job_app_counts, key=lambda k: job_app_counts[k], reverse=True)[:5]

    top_jobs_by_applications: list[TopJobItem] = []
    if top5_ids:
        jobs_rows = (
            await db.execute(
                select(Job.id, Job.title).where(Job.id.in_(top5_ids))
            )
        ).all()
        job_titles = {row.id: row.title for row in jobs_rows}

        # Per-job accepted counts (platform + external)
        platform_accepted_per_job_rows = (
            await db.execute(
                select(JobApplication.job_id, func.count(JobApplication.id))
                .where(
                    JobApplication.job_id.in_(top5_ids),
                    JobApplication.status == ApplicationStatus.ACCEPTED,
                )
                .group_by(JobApplication.job_id)
            )
        ).all()

        external_accepted_per_job_rows = (
            await db.execute(
                select(ExternalApplication.job_id, func.count(ExternalApplication.id))
                .where(
                    ExternalApplication.job_id.in_(top5_ids),
                    ExternalApplication.status == ExternalApplicationStatus.ACCEPTED,
                )
                .group_by(ExternalApplication.job_id)
            )
        ).all()

        accepted_per_job: dict = {}
        for job_id, cnt in platform_accepted_per_job_rows:
            accepted_per_job[job_id] = accepted_per_job.get(job_id, 0) + cnt
        for job_id, cnt in external_accepted_per_job_rows:
            accepted_per_job[job_id] = accepted_per_job.get(job_id, 0) + cnt

        for job_id in top5_ids:
            top_jobs_by_applications.append(
                TopJobItem(
                    job_id=str(job_id),
                    title=job_titles.get(job_id, "Unknown"),
                    application_count=job_app_counts[job_id],
                    accepted_count=accepted_per_job.get(job_id, 0),
                )
            )

    # ── APPLICATIONS OVER TIME (last 6 months) ────────────────────────────

    six_months_ago = datetime.now(timezone.utc) - timedelta(days=183)

    platform_monthly_rows = (
        await db.execute(
            select(
                func.date_trunc(literal_column("'month'"), JobApplication.applied_at).label("month"),
                func.count(JobApplication.id).label("count"),
            )
            .where(
                JobApplication.job_id.in_(job_ids_subquery),
                JobApplication.applied_at >= six_months_ago,
            )
            .group_by(func.date_trunc(literal_column("'month'"), JobApplication.applied_at))
        )
    ).all()

    external_monthly_rows = (
        await db.execute(
            select(
                func.date_trunc(literal_column("'month'"), ExternalApplication.uploaded_at).label("month"),
                func.count(ExternalApplication.id).label("count"),
            )
            .where(
                ExternalApplication.job_id.in_(job_ids_subquery),
                ExternalApplication.uploaded_at >= six_months_ago,
            )
            .group_by(func.date_trunc(literal_column("'month'"), ExternalApplication.uploaded_at))
        )
    ).all()

    monthly_counts: dict[str, int] = {}
    for month_dt, count in platform_monthly_rows:
        key = month_dt.strftime("%b %Y")
        monthly_counts[key] = monthly_counts.get(key, 0) + count
    for month_dt, count in external_monthly_rows:
        key = month_dt.strftime("%b %Y")
        monthly_counts[key] = monthly_counts.get(key, 0) + count

    # Generate all 6 month labels so the chart always has 6 points
    now = datetime.now(timezone.utc)
    ordered_months: list[str] = []
    for i in range(5, -1, -1):
        # Go back i months from current month
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        label = datetime(year, month, 1).strftime("%b %Y")
        ordered_months.append(label)

    applications_over_time = [
        MonthlyApplicationItem(month=m, count=monthly_counts.get(m, 0))
        for m in ordered_months
    ]

    # ── JOB STATUS DISTRIBUTION ───────────────────────────────────────────

    job_status_rows = (
        await db.execute(
            select(Job.status, func.count(Job.id))
            .where(Job.recruiter_id == recruiter_id)
            .group_by(Job.status)
        )
    ).all()

    job_status_counts: dict[str, int] = {}
    for status_enum, count in job_status_rows:
        job_status_counts[status_enum.value] = count

    job_status_distribution = [
        JobStatusItem(status=s, count=job_status_counts.get(s, 0))
        for s in ["OPEN", "CLOSED", "DRAFT"]
    ]

    # ── APPLICATION SOURCE BREAKDOWN ──────────────────────────────────────

    platform_count_result = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.job_id.in_(job_ids_subquery)
        )
    )
    platform_source_count = platform_count_result.scalar() or 0

    external_source_rows = (
        await db.execute(
            select(ExternalApplication.source, func.count(ExternalApplication.id))
            .where(ExternalApplication.job_id.in_(job_ids_subquery))
            .group_by(ExternalApplication.source)
        )
    ).all()

    external_source_counts: dict[str, int] = {}
    for source_enum, count in external_source_rows:
        external_source_counts[source_enum.value] = count

    application_source_breakdown = [
        ApplicationSourceItem(source="PLATFORM", count=platform_source_count),
    ] + [
        ApplicationSourceItem(source=s, count=external_source_counts.get(s, 0))
        for s in [src.value for src in ExternalApplicationSource]
    ]

    return RecruiterDashboardResponse(
        summary=summary,
        application_status_breakdown=application_status_breakdown,
        top_jobs_by_applications=top_jobs_by_applications,
        applications_over_time=applications_over_time,
        job_status_distribution=job_status_distribution,
        application_source_breakdown=application_source_breakdown,
    )
