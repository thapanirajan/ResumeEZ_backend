from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── KPI block ─────────────────────────────────────────────────────────────────

class CandidateKPI(BaseModel):
    total_applications: int
    pending: int
    shortlisted: int          # REVIEWING
    accepted: int
    rejected: int
    total_resumes: int
    total_skill_gap_reports: int
    avg_ai_score: Optional[float]        # average across scored applications
    avg_match_percentage: Optional[float]  # average skill-gap match %
    profile_score: Optional[int]


# ── Chart data shapes ─────────────────────────────────────────────────────────

class StatusBreakdownItem(BaseModel):
    status: str    # PENDING | REVIEWING | ACCEPTED | REJECTED
    count: int


class WeeklyApplicationItem(BaseModel):
    week: str      # e.g. "Jun 2"
    count: int


class ScoreRangeItem(BaseModel):
    range: str     # e.g. "0–25", "26–50", "51–75", "76–100"
    count: int


class MatchTrendItem(BaseModel):
    label: str     # e.g. "May 12" — date of the report
    match_pct: float


class TopMissingSkillItem(BaseModel):
    skill: str
    count: int


# ── Recent activity ───────────────────────────────────────────────────────────

class RecentApplicationItem(BaseModel):
    id: str
    job_title: str
    company_name: Optional[str]
    status: str
    ai_score: Optional[int]
    applied_at: datetime


# ── Top-level response ────────────────────────────────────────────────────────

class CandidateDashboardResponse(BaseModel):
    # Profile snapshot
    full_name: Optional[str]
    current_role: Optional[str]
    location: Optional[str]
    profile_score: Optional[int]
    skills: list[str]

    # KPIs
    kpi: CandidateKPI

    # Charts
    status_breakdown: list[StatusBreakdownItem]
    weekly_applications: list[WeeklyApplicationItem]
    score_distribution: list[ScoreRangeItem]
    match_trend: list[MatchTrendItem]
    top_missing_skills: list[TopMissingSkillItem]

    # Table
    recent_applications: list[RecentApplicationItem]
