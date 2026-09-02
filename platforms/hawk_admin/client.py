"""机器标注平台客户端。"""

from __future__ import annotations

from framework.http.client import ApiClient


class HawkAdminClient(ApiClient):
    def list_projects(self, *, page: int = 1, page_size: int = 10):
        return self.get("/api/v1/project", params={"page": page, "pageSize": page_size})

    def get_rsa(self):
        return self.get("/api/v1/user/rsa")
