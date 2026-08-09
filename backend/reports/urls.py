from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("sales/", views.sales_report, name="sales_report"),
    path("sales/pdf/", views.sales_report_pdf, name="sales_report_pdf"),
    path("sales/excel/", views.sales_report_excel, name="sales_report_excel"),
]
