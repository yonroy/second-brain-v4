"""Truy vấn API báo cáo nội bộ."""
import os

from src import http

BASE_URL = "https://reports.internal:8443/v2"


def fetch_report(report_id):
    return http.http_get(f"{BASE_URL}/reports/{report_id}", headers={"X-Api-Key": os.environ["REPORTS_KEY"]})
