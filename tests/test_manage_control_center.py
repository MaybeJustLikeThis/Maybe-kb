from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_manage_defaults_to_health_tab_and_renders_system_health() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "import SystemHealth from '../components/SystemHealth.vue'" in manage
    assert "const activeTab = ref('health')" in manage
    assert "{ key: 'health', label: 'Health' }" in manage
    assert 'v-if="activeTab === \'health\'"' in manage
    assert "<SystemHealth" in manage
    assert ':health="health"' in manage
    assert ':rebuilding="reindexing"' in manage
    assert '@rebuild="handleReindex"' in manage


def test_manage_loads_health_and_source_config() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "api.getHealth()" in manage
    assert "api.getSources()" in manage
    assert "loadHealthData" in manage
    assert "refreshManageData" in manage
    assert ">Refresh<" in manage or "Refresh" in manage
    assert '@click="refreshManageData"' in manage
    assert "sourceRows" in manage
    assert "sourceConfigByName" in manage
    assert "sourceConfigError" in manage
    assert "Source config unavailable" in manage


def test_manage_rebuild_feedback_is_visible_and_stateful() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "const reindexing = ref(false)" in manage
    assert "const notice = ref" in manage
    assert "Index rebuilt" in manage
    assert "Index rebuilt, but refresh failed" in manage
    assert "Index rebuild failed" in manage
    assert "Rebuilding..." in manage
    assert "notice-success" in manage
    assert "notice-error" in manage
    assert "await api.triggerIndex()" in manage
    assert "await refreshOperationalData()" in manage


def test_manage_rebuild_operational_refresh_rethrows_health_failure() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "throwOnError?: boolean" in manage
    assert "loadHealthData({ throwOnError: true })" in manage
    assert "if (options?.throwOnError) throw e" in manage


def test_manage_sources_use_configured_labels_and_descriptions() -> None:
    manage = read("web/src/pages/ManagePage.vue")

    assert "source.label || source.name" in manage
    assert "source.description" in manage
    assert "source.icon" in manage
    assert "source.count" in manage
    assert "`/source/${encodeURIComponent(source.name)}`" in manage
    assert ".sort" in manage
    assert "b.count - a.count" in manage
