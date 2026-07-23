from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from pr_agent.algo.utils import PRReviewMarker, convert_to_markdown_v2
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.git_provider import GitProvider
from pr_agent.i18n import gettext, get_translation, normalize_locale


def test_normalize_locale():
    assert normalize_locale("zh-tw") == "zh_TW"
    assert normalize_locale("pt_BR.UTF-8") == "pt_BR"
    assert normalize_locale("en") == "en"
    assert normalize_locale("not-a-locale") == "en_US"


def test_gettext_uses_catalog_and_falls_back_to_english():
    assert gettext("Preparing review...", locale="zh-TW") == "正在準備審閱……"
    assert gettext("Preparing review...", locale="fr-FR") == "Preparing review..."
    assert gettext("Uncatalogued message", locale="zh-TW") == "Uncatalogued message"


def test_translation_objects_are_cached_by_normalized_locale():
    get_translation.cache_clear()
    assert get_translation("zh_TW") is get_translation("zh_TW")


def test_explicit_locales_do_not_leak_between_concurrent_calls():
    locales = ["zh-TW", "en-US"] * 20
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda locale: gettext("Preparing answer...", locale=locale), locales))

    assert results[::2] == ["正在準備回答……"] * 20
    assert results[1::2] == ["Preparing answer..."] * 20


def test_shared_review_renderer_uses_configured_locale():
    settings = get_settings()
    original_locale = settings.config.response_language
    try:
        settings.config.response_language = "zh-TW"
        result = convert_to_markdown_v2({"review": {"security_concerns": "No"}})
    finally:
        settings.config.response_language = original_locale

    assert "未發現安全性疑慮" in result
    assert result.startswith("## PR 審閱指南")
    assert "<!-- pr-agent:review -->" in result


def test_walkthrough_headings_use_configured_locale():
    from pr_agent.tools.pr_description import PRDescription

    settings = get_settings()
    original_locale = settings.config.response_language
    tool = PRDescription.__new__(PRDescription)
    tool.data = {
        "type": "Enhancement",
        "description": "Description text",
        "changes_diagram": "diagram",
        "pr_files": [],
    }
    tool.file_label_dict = []
    tool.vars = {"title": "Title"}
    tool.git_provider = type("Provider", (), {"is_supported": lambda self, feature: True})()
    tool.process_pr_files_prediction = lambda body, value: ("table", [])
    try:
        settings.config.response_language = "zh-TW"
        _, body, walkthrough, _ = tool._prepare_pr_answer()
    finally:
        settings.config.response_language = original_locale

    assert "### **PR 類型**" in body
    assert "### **描述**" in body
    assert "### 圖表導覽" in body
    assert "data-pr-agent-section=\"file-walkthrough\"" in walkthrough
    assert "檔案導覽" in walkthrough


def test_user_description_heading_uses_configured_locale():
    from pr_agent.tools.pr_description import PRDescription

    settings = get_settings()
    original_locale = settings.config.response_language
    tool = PRDescription.__new__(PRDescription)
    tool.data = {"User Description": "Original body from user"}
    tool.vars = {"title": "Title"}
    tool.git_provider = type("Provider", (), {"is_supported": lambda self, feature: False})()
    try:
        settings.config.response_language = "zh-TW"
        _, body, _, _ = tool._prepare_pr_answer()
    finally:
        settings.config.response_language = original_locale

    assert "### **使用者描述**" in body


def test_persistent_review_migrates_legacy_heading_to_marker():
    settings = get_settings()
    original_locale = settings.config.response_language
    old_comment = MagicMock()
    old_comment.body = "## PR Reviewer Guide 🔍\n\nOld review"
    provider = MagicMock()
    provider.get_issue_comments.return_value = [old_comment]
    provider.get_latest_commit_url.return_value = "https://example.test/commit/abcdef1"
    provider.get_comment_url.return_value = "https://example.test/comment/1"
    new_body = f"## PR 審閱指南 🔍\n\n{PRReviewMarker.REGULAR.value}\n\nNew review"

    try:
        settings.config.response_language = "zh-TW"
        GitProvider.publish_persistent_comment_full(
            provider,
            new_body,
            PRReviewMarker.REGULAR.value,
            final_update_message=False,
        )
    finally:
        settings.config.response_language = original_locale

    updated_body = provider.edit_comment.call_args.args[1]
    assert updated_body.startswith("## PR 審閱指南")
    assert PRReviewMarker.REGULAR.value in updated_body
    assert "審閱已更新至提交 https://example.test/commit/abcdef1" in updated_body
