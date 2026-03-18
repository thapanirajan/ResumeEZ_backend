from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_jobs: int
    total_applications: int
    accepted_count: int
    pending_count: int


class ApplicationStatusItem(BaseModel):
    status: str  # "PENDING" | "REVIEWING" | "ACCEPTED" | "REJECTED"
    count: int


class TopJobItem(BaseModel):
    job_id: str
    title: str
    application_count: int
    accepted_count: int


class MonthlyApplicationItem(BaseModel):
    month: str  # e.g. "Jan 2026"
    count: int


class JobStatusItem(BaseModel):
    status: str  # "OPEN" | "CLOSED" | "DRAFT"
    count: int


class ApplicationSourceItem(BaseModel):
    source: str  # "PLATFORM" | "EMAIL" | "LINKEDIN" | "REFERRAL" | "OFFLINE" | "OTHER"
    count: int


class RecruiterDashboardResponse(BaseModel):
    summary: DashboardSummary
    application_status_breakdown: list[ApplicationStatusItem]
    top_jobs_by_applications: list[TopJobItem]
    applications_over_time: list[MonthlyApplicationItem]
    job_status_distribution: list[JobStatusItem]
    application_source_breakdown: list[ApplicationSourceItem]
