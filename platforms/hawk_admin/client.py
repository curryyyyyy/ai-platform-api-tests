"""机器标注平台客户端。"""

from __future__ import annotations

import time

from framework.http.client import ApiClient


class HawkAdminClient(ApiClient):
    def list_projects(self, *, page: int = 1, page_size: int = 10, **params):
        return self.get(
            "/api/v1/project", params={"page": page, "pageSize": page_size, **params}
        )

    def get_rsa(self):
        return self.get("/api/v1/user/rsa")

    def user_auth(self, *, token: str):
        return self.post("/api/v1/user/auth", json={"token": token})

    def user_login(self, **payload):
        return self.post("/api/v1/user/login", json=payload)

    def user_logout(self, *, token: str):
        return self.post("/api/v1/user/logout", json={"token": token})

    # 项目
    def create_project(self, **payload):
        return self.post("/api/v1/project", json=payload)

    def get_project(self, project_id):
        return self.get(f"/api/v1/project/{project_id}")

    def update_project(self, project_id, **payload):
        return self.put(f"/api/v1/project/{project_id}", json={"id": project_id, **payload})

    def delete_project(self, project_id):
        return self.delete(f"/api/v1/project/{project_id}")

    def favorite_project(self, project_id):
        return self.post(f"/api/v1/project/{project_id}/favorite")

    def unfavorite_project(self, project_id):
        return self.delete(f"/api/v1/project/{project_id}/favorite")

    # 阶段
    def list_stages(self, **params):
        return self.get("/api/v1/stage", params=params)

    def create_stage(self, **payload):
        return self.post("/api/v1/stage", json=payload)

    def get_stage(self, stage_id):
        return self.get(f"/api/v1/stage/{stage_id}")

    def update_stage(self, stage_id, **payload):
        return self.put(f"/api/v1/stage/{stage_id}", json={"id": stage_id, **payload})

    def delete_stage(self, stage_id):
        return self.delete(f"/api/v1/stage/{stage_id}")

    # 流程
    def list_flows(self, **params):
        return self.get("/api/v1/flow", params=params)

    def create_flow(self, **payload):
        return self.post("/api/v1/flow", json=payload)

    def get_flow(self, flow_id):
        return self.get(f"/api/v1/flow/{flow_id}")

    def update_flow(self, flow_id, **payload):
        return self.put(f"/api/v1/flow/{flow_id}", json={"id": flow_id, **payload})

    def delete_flow(self, flow_id):
        return self.delete(f"/api/v1/flow/{flow_id}")

    # 批次
    def list_batches(self, **params):
        return self.get("/api/v1/batch", params=params)

    def create_batch(self, **payload):
        return self.post("/api/v1/batch", json=payload)

    def get_batch(self, batch_id):
        return self.get(f"/api/v1/batch/{batch_id}")

    def update_batch(self, batch_id, **payload):
        return self.put(f"/api/v1/batch/{batch_id}", json={"id": batch_id, **payload})

    def delete_batch(self, batch_id):
        return self.delete(f"/api/v1/batch/{batch_id}")

    def check_batch_name(self, project_id, name):
        return self.get("/api/v1/batch-name/check", params={"project_id": project_id, "name": name})

    def update_batch_status(self, batch_id, status):
        return self.put(f"/api/v1/batch/{batch_id}/status", json={"id": batch_id, "status": status})

    def update_batch_input(self, batch_id, **payload):
        return self.put(f"/api/v1/batch/{batch_id}/input", json={"id": batch_id, **payload})

    def flowgraph(self, batch_id):
        return self.get(f"/api/v1/batch/{batch_id}/flowgraph")

    def batch_statistics(self, **payload):
        return self.post("/api/v1/batch/statistics", json=payload)

    def list_statistics_batches(self, **params):
        return self.get("/api/v1/batch/statistics/list", params=params)

    def statistics_batch_csv(self, batch_id):
        return self.get(f"/api/v1/batch/statistics/{batch_id}/csv")

    def upload_file(self, payload: str = ""):
        """上传接口的 OpenAPI 请求体是原始 JSON string，而非 JSON object。"""
        return self.post("/api/v1/batch/upload", json=payload)

    def init_multipart_upload(self, **payload):
        return self.post("/api/v1/batch/upload/multipart/init", json=payload)

    def complete_multipart_upload(self, **payload):
        return self.post("/api/v1/batch/upload/multipart/complete", json=payload)

    def copy_batch(self, source_id, **payload):
        return self.post(f"/api/v1/batch/{source_id}/copy", json=payload)

    def download_url(self, **payload):
        return self.post("/api/v1/files/download-url", json=payload)

    def list_temp_files(self, **params):
        return self.get("/api/v1/files/temp", params=params)

    def csv_first_row(self, *, tos_path):
        return self.get("/api/v1/tools/csv_first_row", params={"tosPath": tos_path})

    def trigger_daily_metrics(self, **payload):
        return self.post("/api/v1/tools/daily_metrics/trigger", json=payload)

    def hbase_ddl(self, *, datatype):
        return self.get("/api/v1/tools/hbase_ddl", params={"datatype": datatype})

    def refresh_stage_ref_counts(self, **payload):
        return self.post("/api/v1/tools/stage/ref_counts/refresh", json=payload)

    def csv_info(self, **payload):
        return self.post("/api/v1/tools/csv_info", json=payload)

    def common_templates(self):
        return self.get("/api/v1/common-template")

    def list_credentials(self, **params):
        return self.get("/api/v1/credential", params=params)

    def create_credential(self, **payload):
        return self.post("/api/v1/credential", json=payload)

    def update_credential(self, credential_id, **payload):
        return self.put(f"/api/v1/credential/{credential_id}", json={"id": credential_id, **payload})

    def delete_credential(self, credential_id):
        return self.delete(f"/api/v1/credential/{credential_id}")

    def feishu_project_info(self, *, link: str):
        return self.get("/api/v1/project/feishu/info", params={"link": link})

    # Hawk 执行和查询
    def operate_batch(self, batch_id, operation):
        return self.post("/api/v1/hawk/operate", json={"batchId": batch_id, "operation": operation})

    def operate_batch_with_retry(self, batch_id, operation, *, retries: int = 5, backoff: float = 0.4):
        """执行批次操作并重试下游节点锁的瞬态冲突。

        tc-hawk 在 PAUSE/RESTART 的节点清理窗口内会返回
        ``lock already taken``。该响应不是非法状态转换，短暂等待后重试即可；
        其他业务错误保持原样返回，避免掩盖真实失败。
        """
        response = None
        for attempt in range(retries + 1):
            response = self.operate_batch(batch_id, operation)
            body = self.json(response)
            message = str(body.get("message", ""))
            if body.get("code") != 1 or not message.startswith("lock already taken") or attempt >= retries:
                return response
            time.sleep(backoff * (attempt + 1))
        return response  # pragma: no cover - loop always returns

    def batch_stat(self, batch_id, **kwargs):
        return self.get(f"/api/v1/hawk/stat/{batch_id}", **kwargs)

    def batch_stats(self, batch_ids, **kwargs):
        return self.post("/api/v1/hawk/stats", json={"batchIds": batch_ids}, **kwargs)

    # 资源成本看板（REQ-RCB-20260910）
    def get_project_cost_detail(self, project_id, **kwargs):
        return self.get(f"/api/v1/hawk/cost/projects/{project_id}/detail", **kwargs)

    def get_batch_cost_detail(self, batch_id, **kwargs):
        return self.get(f"/api/v1/hawk/cost/batches/{batch_id}/detail", **kwargs)

    def get_stage_cost_detail(self, batch_id, stage_index, **kwargs):
        return self.get(f"/api/v1/hawk/cost/batches/{batch_id}/stages/{stage_index}", **kwargs)

    def task_stream(self, **params):
        return self.get("/api/v1/hawk/task-stream", params=params)

    def error_log(self, batch_id):
        return self.get(f"/api/v1/hawk/error-log/{batch_id}")

    def key_fields(self, batch_id):
        return self.get(f"/api/v1/hawk/key-fields/{batch_id}")

    def output_fields(self, batch_id):
        return self.get(f"/api/v1/hawk/output-fields/{batch_id}")

    def export_output(self, batch_id):
        return self.post("/api/v1/hawk/output", json={"batchId": batch_id})

    def done_end_delete(self, batch_id, *, action_token=""):
        return self.get(f"/api/v1/hawk/done-end-alert/delete/{batch_id}", params={"actionToken": action_token})

    def done_end_rollback(self, batch_id, *, action_token=""):
        return self.get(f"/api/v1/hawk/done-end-alert/rollback/{batch_id}", params={"actionToken": action_token})

    def done_end_allow_empty_output(self, batch_id):
        return self.post(f"/api/v1/hawk/done-end-alert/allow-empty-output/{batch_id}")

    def system_load(self):
        return self.get("/api/v1/hawk/system-load")

    def hide_task_stream_batch(self, **payload):
        return self.post("/api/v1/hawk/task-stream/hidden", json=payload)

    def refresh_task_stream(self, **payload):
        return self.post("/api/v1/hawk/task-stream/stats", json=payload)

    def list_templates(self, **params):
        return self.get("/api/v1/tpl/wf", params=params)

    def create_template(self, **payload):
        return self.post("/api/v1/tpl/wf", json=payload)

    def batch_get_templates(self, ids):
        return self.post("/api/v1/tpl/wf/batch-get", json={"ids": ids})

    def create_empty_template(self, **payload):
        return self.post("/api/v1/tpl/wf/empty", json=payload)

    def template_metric(self, ids):
        return self.get("/api/v1/tpl/wf/metric", params={"ids": ids})

    def get_template(self, template_id):
        return self.get(f"/api/v1/tpl/wf/{template_id}")

    def update_template(self, template_id, **payload):
        return self.put(f"/api/v1/tpl/wf/{template_id}", json={"id": template_id, **payload})

    def complete_template(self, template_id, **payload):
        return self.post(
            f"/api/v1/tpl/wf/{template_id}/complete", json={"id": template_id, **payload}
        )

    def download_template(self, template_id):
        return self.get(f"/api/v1/tpl/wf/{template_id}/download")

    def list_transfer_tasks(self, **params):
        return self.get("/api/v1/transfer/task", params=params)

    def create_transfer_task(self, **payload):
        return self.post("/api/v1/transfer/task", json=payload)

    def get_transfer_task(self, task_id):
        return self.get(f"/api/v1/transfer/task/{task_id}")

    def _transfer_action(self, task_id, action, **payload):
        return self.post(f"/api/v1/transfer/task/{task_id}/{action}", json=payload)

    def cancel_transfer_task(self, task_id, **payload):
        return self._transfer_action(task_id, "cancel", **payload)

    def close_transfer_task(self, task_id, **payload):
        return self._transfer_action(task_id, "close", **payload)

    def update_transfer_config(self, task_id, **payload):
        return self.put(f"/api/v1/transfer/task/{task_id}/config", json={"id": task_id, **payload})

    def pause_transfer_task(self, task_id, **payload):
        return self._transfer_action(task_id, "pause", **payload)

    def run_transfer_task(self, task_id, **payload):
        return self._transfer_action(task_id, "run", **payload)

    def transfer_snapshot(self, task_id, **payload):
        return self._transfer_action(task_id, "snapshot", **payload)

    def continue_transfer_step(self, task_id, step_no, **payload):
        return self.post(f"/api/v1/transfer/task/{task_id}/step/{step_no}/continue", json=payload)

    def retry_transfer_step(self, task_id, step_no, **payload):
        return self.post(f"/api/v1/transfer/task/{task_id}/step/{step_no}/retry", json=payload)
