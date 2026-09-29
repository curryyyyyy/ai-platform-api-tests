from __future__ import annotations

import pytest

from framework.assertions import assert_envelope, assert_rejected
from framework.data.dataset import dataset_case_map, dataset_cases, dataset_defaults


pytestmark = [pytest.mark.live, pytest.mark.hawk_admin]
TEMPLATE_DEFAULTS = dataset_defaults("hawk_admin", "template_workflow")
TEMPLATE_BATCH_GET_CASES = dataset_case_map("hawk_admin", "template_workflow", "batch_get")
TEMPLATE_INVALID_WRITES = dataset_cases("hawk_admin", "template_workflow", "invalid_write")
TEMPLATE_INVALID_COMPLETE = dataset_case_map(
    "hawk_admin", "template_workflow", "invalid_complete"
)


def test_hawk_07_17_list_template_workflows(platform_client):
    body = assert_envelope(platform_client.list_templates(page=1, pageSize=10), required_keys=("data",))
    data = body["data"]
    assert isinstance(data, dict)
    assert isinstance(data.get("data"), list)


@pytest.mark.requirement(id="REQ-TEMPLATE-WORKFLOW-OWNERSHIP", name="template_workflow_ownership")
@pytest.mark.case_id(
    "REQ-TEMPLATE-WORKFLOW-OWNERSHIP-API-01",
    title="模板工作流归属枚举和归属筛选可用",
)
def test_hawk_10_15_template_workflow_ownership_options_and_filter(platform_client):
    """归属枚举必须可展示，按枚举值筛选时返回记录不得混入其它归属。"""
    options = assert_envelope(
        platform_client.list_template_ownership_options(), required_keys=("data",)
    )["data"]
    assert isinstance(options, list) and options, "归属枚举不应为空"
    option_ids: set[str] = set()
    for option in options:
        assert isinstance(option, dict), f"归属枚举项必须是对象: {option!r}"
        option_id = str(option.get("id", "")).strip()
        assert option_id and isinstance(option.get("name"), str) and option["name"].strip(), option
        assert option_id not in option_ids, f"归属枚举存在重复 ID: {option_id}"
        option_ids.add(option_id)

    selected = str(options[0]["id"])
    listing = assert_envelope(
        platform_client.list_templates(page=1, pageSize=20, ownershipId=selected),
        required_keys=("data",),
    )["data"]
    items = listing.get("data")
    assert isinstance(items, list), f"归属筛选响应 data 应为数组: {listing}"
    assert all(str(item.get("ownershipId", "")) == selected for item in items), listing
    assert all("ownershipName" in item for item in items), listing


@pytest.mark.requirement(id="REQ-TEMPLATE-WORKFLOW-OWNERSHIP", name="template_workflow_ownership")
@pytest.mark.case_id(
    "REQ-TEMPLATE-WORKFLOW-OWNERSHIP-API-02",
    title="模板工作流写入接口拒绝不存在的归属编号",
)
def test_hawk_10_16_template_workflow_rejects_unknown_ownership(platform_client):
    """归属校验必须在创建或更新持久化前完成，避免产生脏工作流记录。"""
    unknown = "XM-NOT-EXIST"
    assert_rejected(
        platform_client.create_empty_template(name="ownership-validation", ownershipId=unknown)
    )
    assert_rejected(platform_client.complete_template(1, ownershipId=unknown))
    assert_rejected(platform_client.update_template(1, ownershipId=unknown))


@pytest.mark.requirement(id="REQ-TEMPLATE-WORKFLOW-LIFECYCLE", name="template_workflow_lifecycle")
@pytest.mark.case_id("REQ-TEMPLATE-WORKFLOW-LIFECYCLE-API-01", title="批量查询模板工作流过滤非法编号并保留有效条目")
def test_hawk_10_07_batch_get_template_workflows(platform_client):
    empty_body = assert_envelope(
        platform_client.batch_get_templates(TEMPLATE_BATCH_GET_CASES["empty"]["ids"]),
        required_keys=("data",),
    )
    assert empty_body["data"] == []
    invalid_body = assert_envelope(
        platform_client.batch_get_templates([0, -1, 0]), required_keys=("data",)
    )
    assert invalid_body["data"] == []

    listing = assert_envelope(
        platform_client.list_templates(page=1, pageSize=1), required_keys=("data",)
    )["data"]
    templates = listing.get("data")
    assert isinstance(templates, list)
    if not templates:
        return
    template = templates[0]
    template_id = int(template["id"])
    body = assert_envelope(
        platform_client.batch_get_templates([template_id, 0, -1, template_id]),
        required_keys=("data",),
    )
    assert len(body["data"]) == 1
    brief = body["data"][0]
    assert int(brief["id"]) == template_id
    assert brief["name"] == template["name"]
    assert brief.get("description", "") == template.get("description", "")


@pytest.mark.parametrize("case", TEMPLATE_INVALID_WRITES, ids=lambda case: case["id"])
def test_hawk_07_11_invalid_template_write_is_rejected(case, platform_client):
    assert_rejected(platform_client.create_template(**case["payload"]))


def test_hawk_07_13_missing_template_operations_are_rejected(platform_client):
    template_id = TEMPLATE_DEFAULTS["missingId"]
    assert_rejected(platform_client.get_template(template_id))
    assert_rejected(platform_client.update_template(template_id))
    assert_rejected(platform_client.download_template(template_id))


def test_hawk_template_metric_returns_zero_for_missing_template(platform_client):
    """指标接口是聚合查询，不存在的模板应返回明确的零值指标。"""
    data = assert_envelope(
        platform_client.template_metric([str(TEMPLATE_DEFAULTS["missingId"])]),
        required_keys=("data",),
    )["data"]
    assert isinstance(data, dict)
    for field in ("total", "running", "finished", "resourceNum"):
        assert int(data[field]) == 0, f"不存在模板的聚合指标 {field} 应为 0: {data}"


@pytest.mark.requirement(id="REQ-TEMPLATE-WORKFLOW-LIFECYCLE", name="template_workflow_lifecycle")
@pytest.mark.case_id("REQ-TEMPLATE-WORKFLOW-LIFECYCLE-API-02", title="创建空模板工作流拒绝空任务名称")
def test_hawk_10_08_create_empty_template_requires_name(platform_client):
    assert_rejected(platform_client.create_empty_template())


@pytest.mark.requirement(id="REQ-TEMPLATE-WORKFLOW-LIFECYCLE", name="template_workflow_lifecycle")
@pytest.mark.case_id("REQ-TEMPLATE-WORKFLOW-LIFECYCLE-API-03", title="补齐模板工作流拒绝无效工作流编号")
def test_hawk_10_09_complete_template_requires_existing_workflow(platform_client):
    template_id = TEMPLATE_INVALID_COMPLETE["missing_workflow"]["workflow_id"]
    assert_rejected(platform_client.complete_template(template_id))
