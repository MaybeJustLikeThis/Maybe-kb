from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_api_exposes_system_health_client() -> None:
    api_ts = read("web/src/api.ts")
    assert "export type HealthStatus" in api_ts
    assert "interface HealthCheck" in api_ts
    assert "interface SystemHealth" in api_ts
    assert "getHealth()" in api_ts
    assert "request<SystemHealth>('/health')" in api_ts


def test_overview_renders_system_health_panel() -> None:
    component = read("web/src/components/SystemHealth.vue")
    overview = read("web/src/pages/OverviewPage.vue")
    assert "System Health" in component
    assert "Needs attention" in component
    assert "Setup issue" in component
    assert "Rebuild index" in component
    assert "SystemHealth" in overview
    assert "api.getHealth()" in overview
