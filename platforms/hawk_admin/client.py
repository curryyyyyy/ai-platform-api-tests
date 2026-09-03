"""机器标注平台客户端。"""

from __future__ import annotations

import time

from framework.http.client import ApiClient


class HawkAdminClient(ApiClient):
    def list_projects(self, *, page: int = 1, page_size: int = 10):
        return self.get("/api/v1/project", params={"page": page, "pageSize": page_size})

    def get_rsa(self):
        return self.get("/api/v1/user/rsa")

    # 项目
    def create_project(self, **payload):
        return self.post("/api/v1/project", json=payload)

    def get_project(self, project_id):
        return self.get(f"/api/v1/project/{project_id}")

    def update_project(self, project_id, **payload):
        return self.put(f"/api/v1/project/{project_id}", json={"id": project_id, **payload})

    def delete_project(self, project_id):
        return self.delete(f"/api/v1/project/{project_id}")

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

    # Hawk 执行和查询
    def operate_batch(self, batch_id, operation):
        return self.post("/api/v1/hawk/operate", json={"batchId": batch_id, "operation": operation})

    def operate_batch_with_retry(self, batch_id, operation, *, retries: int = 5, backoff: float = 0.4):
        """执行批次操作并重试下游节点锁的瞬态冲突。

        tc-hawk 在 PAUSE/RESTART 的节点清理窗口内会返回
        ``lock already taken``。该响应不是非法状态转换，短暂等待后重试即可；
        其他业务错误保持原样返回，避免掩盖真实失败。
        """
        for attempt in range(retries + 1):
            response = self.operate_batch(batch_id, operation)
            body = self.json(response)
            message = str(body.get("message", ""))
            if body.get("code") != 1 or not message.startswith("lock already taken") or attempt >= retries:
                return response
            time.sleep(backoff * (attempt + 1))
        return response  # pragma: no cover - loop always returns

    def batch_stat(self, batch_id):
        return self.get(f"/api/v1/hawk/stat/{batch_id}")

    def batch_stats(self, batch_ids):
        return self.post("/api/v1/hawk/stats", json={"batchIds": batch_ids})

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
