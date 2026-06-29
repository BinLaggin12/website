import hashlib
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import Database
from .schemas import (
    PatientCreate, PatientResponse,
    BookingCreate, BookingResponse,
    BookingStatusUpdate,
    DoctorResponse, TestResponse,
    ReportCreate, ReportResponse,
    AdminLogin, AdminTokenResponse,
    AdminDashboardResponse,
    DoctorUpdate, TestUpdate,
    AdminBookingStatusUpdate, AdminReportCreate,
)


ROOT_DIR = Path(__file__).resolve().parent.parent.parent

ADMIN_TOKENS: dict[str, str] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _static_file_response(path: str):
    full = ROOT_DIR / path
    if full.exists() and full.is_file():
        return FileResponse(str(full))
    full = ROOT_DIR / "index.html"
    if full.exists():
        return FileResponse(str(full))
    raise HTTPException(404, "Not found")


def create_fastapi_app(database: Database) -> FastAPI:
    app = FastAPI(title="Unicus Diagnostics", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.database = database

    # --- Auth helpers ---

    def require_admin(authorization: str | None = Header(None)):
        if not authorization:
            raise HTTPException(401, "Unauthorized")
        token = authorization.replace("Bearer ", "")
        if token not in ADMIN_TOKENS:
            raise HTTPException(401, "Invalid token")
        return ADMIN_TOKENS[token]

    # --- Auth endpoints ---

    @app.post("/api/admin/login")
    def admin_login(body: AdminLogin):
        user = database.get_admin_user(body.username)
        if not user:
            raise HTTPException(401, "Invalid credentials")
        if user["password_hash"] != _hash_password(body.password):
            raise HTTPException(401, "Invalid credentials")
        token = str(uuid.uuid4())
        ADMIN_TOKENS[token] = body.username
        return AdminTokenResponse(token=token, username=body.username, role=user["role"])

    @app.post("/api/admin/logout")
    def admin_logout(authorization: str | None = Header(None)):
        if authorization:
            token = authorization.replace("Bearer ", "")
            ADMIN_TOKENS.pop(token, None)
        return {"status": "ok"}

    # --- Admin dashboard ---

    @app.get("/api/admin/dashboard")
    def admin_dashboard(_=Depends(require_admin)):
        return AdminDashboardResponse(
            total_patients=database.get_all_patients_count(),
            total_bookings=database.get_all_bookings_count(),
            todays_bookings=database.get_todays_bookings_count(),
        )

    # --- Admin patient list ---

    @app.get("/api/admin/patients")
    def admin_list_patients(_=Depends(require_admin)):
        return database.list_all_patients()

    # --- Admin booking list & update ---

    @app.get("/api/admin/bookings")
    def admin_list_bookings(_=Depends(require_admin)):
        return database.list_all_bookings()

    @app.put("/api/admin/booking/{booking_id}/status")
    def admin_update_booking_status(booking_id: str, body: AdminBookingStatusUpdate, _=Depends(require_admin)):
        database.update_booking_status(booking_id, body.status)
        return {"status": "ok"}

    # --- Admin reports ---

    @app.get("/api/admin/reports")
    def admin_list_reports(_=Depends(require_admin)):
        return database.list_all_reports()

    @app.post("/api/admin/report/create")
    def admin_create_report(body: AdminReportCreate, _=Depends(require_admin)):
        booking = database.get_booking(body.booking_id)
        if not booking:
            raise HTTPException(404, "Booking not found")
        report = database.create_report(
            body.booking_id,
            str(booking.patient_id),
            booking.test_name,
            body.results,
        )
        return {
            "report_id": str(report.report_id),
            "booking_id": str(report.booking_id),
            "test_name": report.test_name,
            "results": report.results,
            "generated_at": report.generated_at,
        }

    @app.put("/api/admin/report/{report_id}")
    def admin_update_report(report_id: str, body: ReportCreate, _=Depends(require_admin)):
        database.update_report(report_id, body.results)
        return {"status": "ok"}

    # --- Admin doctors ---

    @app.put("/api/admin/doctor/{doctor_id}")
    def admin_update_doctor(doctor_id: str, body: DoctorUpdate, _=Depends(require_admin)):
        database.update_doctor(doctor_id, body.name, body.speciality, body.qualifications, body.bio)
        return {"status": "ok"}

    # --- Admin tests ---

    @app.put("/api/admin/test/{test_id}")
    def admin_update_test(test_id: str, body: TestUpdate, _=Depends(require_admin)):
        database.update_test(test_id, body.name, body.price, body.description, body.category)
        return {"status": "ok"}

    # --- Patient endpoints ---

    @app.post("/api/patient/create", response_model=PatientResponse)
    def create_patient(body: PatientCreate):
        existing = database.get_patient_by_phone(body.phone)
        if existing:
            return PatientResponse(
                patient_id=str(existing.patient_id),
                name=existing.name,
                phone=existing.phone,
                address=existing.address,
                created_at=existing.created_at,
            )
        patient = database.create_patient(body.name, body.phone, body.address)
        return PatientResponse(
            patient_id=str(patient.patient_id),
            name=patient.name,
            phone=patient.phone,
            address=patient.address,
            created_at=patient.created_at,
        )

    @app.get("/api/patient/phone/{phone}", response_model=PatientResponse)
    def get_patient_by_phone(phone: str):
        patient = database.get_patient_by_phone(phone)
        if not patient:
            raise HTTPException(404, "Patient not found")
        return PatientResponse(
            patient_id=str(patient.patient_id),
            name=patient.name,
            phone=patient.phone,
            address=patient.address,
            created_at=patient.created_at,
        )

    @app.get("/api/patient/{patient_id}", response_model=PatientResponse)
    def get_patient(patient_id: str):
        patient = database.get_patient(patient_id)
        if not patient:
            raise HTTPException(404, "Patient not found")
        return PatientResponse(
            patient_id=str(patient.patient_id),
            name=patient.name,
            phone=patient.phone,
            address=patient.address,
            created_at=patient.created_at,
        )

    # --- Booking endpoints ---

    @app.post("/api/booking/create", response_model=BookingResponse)
    def create_booking(body: BookingCreate):
        patient = database.get_patient_by_phone(body.patient_phone)
        if not patient:
            patient = database.create_patient(body.patient_name, body.patient_phone, body.collection_address)
        booking = database.create_booking(
            str(patient.patient_id),
            body.patient_name,
            body.patient_phone,
            body.test_name,
            body.collection_address,
        )
        return BookingResponse(
            booking_id=str(booking.booking_id),
            patient_id=str(booking.patient_id),
            patient_name=booking.patient_name,
            patient_phone=booking.patient_phone,
            test_name=booking.test_name,
            collection_address=booking.collection_address,
            status=booking.status,
            created_at=booking.created_at,
        )

    @app.get("/api/booking/{booking_id}", response_model=BookingResponse)
    def get_booking(booking_id: str):
        booking = database.get_booking(booking_id)
        if not booking:
            raise HTTPException(404, "Booking not found")
        return BookingResponse(
            booking_id=str(booking.booking_id),
            patient_id=str(booking.patient_id),
            patient_name=booking.patient_name,
            patient_phone=booking.patient_phone,
            test_name=booking.test_name,
            collection_address=booking.collection_address,
            status=booking.status,
            created_at=booking.created_at,
        )

    @app.get("/api/bookings/{phone}")
    def list_bookings(phone: str):
        bookings = database.list_bookings_by_phone(phone)
        return [
            BookingResponse(
                booking_id=str(b.booking_id),
                patient_id=str(b.patient_id),
                patient_name=b.patient_name,
                patient_phone=b.patient_phone,
                test_name=b.test_name,
                collection_address=b.collection_address,
                status=b.status,
                created_at=b.created_at,
            )
            for b in bookings
        ]

    # --- Doctor endpoints ---

    @app.get("/api/doctors", response_model=list[DoctorResponse])
    def list_doctors():
        doctors = database.list_doctors()
        return [
            DoctorResponse(
                doctor_id=str(d.doctor_id),
                name=d.name,
                speciality=d.speciality,
                qualifications=d.qualifications,
                bio=d.bio,
            )
            for d in doctors
        ]

    # --- Test endpoints ---

    @app.get("/api/tests", response_model=list[TestResponse])
    def list_tests():
        tests = database.list_tests()
        return [
            TestResponse(
                test_id=str(t.test_id),
                name=t.name,
                price=t.price,
                description=t.description,
                category=t.category,
            )
            for t in tests
        ]

    # --- Report endpoints ---

    @app.post("/api/report/create", response_model=ReportResponse)
    def create_report(body: ReportCreate):
        booking = database.get_booking(body.booking_id)
        if not booking:
            raise HTTPException(404, "Booking not found")
        report = database.create_report(
            body.booking_id,
            str(booking.patient_id),
            booking.test_name,
            body.results,
        )
        return ReportResponse(
            report_id=str(report.report_id),
            booking_id=str(report.booking_id),
            patient_id=str(report.patient_id),
            test_name=report.test_name,
            results=report.results,
            generated_at=report.generated_at,
        )

    @app.get("/api/report/{booking_id}")
    def get_report(booking_id: str):
        report = database.get_report_by_booking(booking_id)
        if not report:
            raise HTTPException(404, "Report not found for this booking")
        return ReportResponse(
            report_id=str(report.report_id),
            booking_id=str(report.booking_id),
            patient_id=str(report.patient_id),
            test_name=report.test_name,
            results=report.results,
            generated_at=report.generated_at,
        )

    # --- Seed ---

    @app.post("/api/seed")
    def seed_data():
        database.seed_doctors()
        database.seed_tests()
        return {"status": "ok", "message": "Doctors and tests seeded"}

    # --- Static file serving (catch-all, must be last) ---

    @app.get("/{path:path}")
    def serve_static(path: str):
        full = ROOT_DIR / path
        if full.exists() and full.is_file():
            return FileResponse(str(full))
        idx = ROOT_DIR / "index.html"
        if idx.exists():
            return FileResponse(str(idx))
        raise HTTPException(404, "Not found")

    return app
