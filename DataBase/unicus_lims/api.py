import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .database import Database
from .schemas import (
    PatientCreate, PatientResponse,
    BookingCreate, BookingResponse,
    DoctorResponse, TestResponse,
    ReportCreate, ReportResponse,
)


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_fastapi_app(database: Database) -> FastAPI:
    app = FastAPI(title="Unicus Diagnostics LIMS", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.database = database

    # --- Static files ---
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

        @app.get("/")
        async def serve_index():
            return FileResponse(str(STATIC_DIR / "index.html"))

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

    # --- Seed endpoints ---

    @app.post("/api/seed")
    def seed_data():
        database.seed_doctors()
        database.seed_tests()
        return {"status": "ok", "message": "Doctors and tests seeded"}

    return app
