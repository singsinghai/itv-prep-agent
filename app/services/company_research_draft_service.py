class CompanyResearchDraftService:
    """
    Draft only: planned post-planner stage for external company research.
    This stage is intentionally not wired into runtime execution yet.
    """

    def draft_next_steps(self, company_name: str | None) -> list[str]:
        if not company_name:
            return [
                "Skip Perplexity company research because company is unresolved.",
                "Ask user for company name or proceed with generic interview-prep path.",
            ]
        return [
            f"Use Perplexity to research company profile for '{company_name}' (business, products, recent news).",
            "Extract company-specific interview signals (team focus, product domain, likely priorities).",
            "Feed enriched company context into downstream interview-prep generation stage.",
        ]
