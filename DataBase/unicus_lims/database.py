import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from cassandra.cluster import Cluster
from cassandra.query import PreparedStatement


KEYSPACE = "unicus_lims"
REPLICATION = {"class": "SimpleStrategy", "replication_factor": 2}


@dataclass
class Patient:
    patient_id: uuid.UUID
    name: str
    phone: str
    address: str
    created_at: str


@dataclass
class Booking:
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str
    test_name: str
    collection_address: str
    status: str
    created_at: str


@dataclass
class Doctor:
    doctor_id: uuid.UUID
    name: str
    speciality: str
    qualifications: str
    bio: str


@dataclass
class Test:
    test_id: uuid.UUID
    name: str
    price: float
    description: str
    category: str


@dataclass
class Report:
    report_id: uuid.UUID
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    test_name: str
    results: str
    generated_at: str


@dataclass
class PreparedStatements:
    patient_insert: PreparedStatement = None
    patient_by_id: PreparedStatement = None
    patient_by_phone: PreparedStatement = None

    booking_insert: PreparedStatement = None
    booking_by_id: PreparedStatement = None
    bookings_by_phone: PreparedStatement = None
    bookings_by_phone_insert: PreparedStatement = None
    bookings_by_phone_index: PreparedStatement = None

    doctor_insert: PreparedStatement = None
    doctor_by_id: PreparedStatement = None
    doctor_list: PreparedStatement = None

    test_insert: PreparedStatement = None
    test_by_id: PreparedStatement = None
    test_list: PreparedStatement = None

    report_insert: PreparedStatement = None
    report_by_id: PreparedStatement = None
    report_by_booking: PreparedStatement = None
    report_by_booking_insert: PreparedStatement = None


class Database:
    def __init__(self, hosts: list[str] | None = None):
        self.hosts = hosts or ["127.0.0.1"]
        self.cluster: Cluster | None = None
        self.session = None
        self.prepared = PreparedStatements()
        self._connect_and_init()

    def _connect_and_init(self):
        self.cluster = Cluster(self.hosts)
        self.session = self.cluster.connect()
        self._create_keyspace()
        self.session.set_keyspace(KEYSPACE)
        self._create_tables()
        self._prepare_statements()

    def _execute(self, query: str):
        return self.session.execute(query)

    def _create_keyspace(self):
        self._execute(
            f"CREATE KEYSPACE IF NOT EXISTS {KEYSPACE} "
            f"WITH replication = {REPLICATION}"
        )

    def _create_tables(self):
        self._execute("""
            CREATE TABLE IF NOT EXISTS patients (
                patient_id UUID PRIMARY KEY,
                name TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS patients_by_phone (
                phone TEXT PRIMARY KEY,
                patient_id UUID,
                name TEXT,
                address TEXT,
                created_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id UUID PRIMARY KEY,
                patient_id UUID,
                patient_name TEXT,
                patient_phone TEXT,
                test_name TEXT,
                collection_address TEXT,
                status TEXT,
                created_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS bookings_by_phone (
                phone TEXT,
                booking_id UUID,
                patient_name TEXT,
                test_name TEXT,
                status TEXT,
                created_at TIMESTAMP,
                PRIMARY KEY ((phone), booking_id)
            ) WITH CLUSTERING ORDER BY (booking_id DESC)
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                doctor_id UUID PRIMARY KEY,
                name TEXT,
                speciality TEXT,
                qualifications TEXT,
                bio TEXT
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS tests (
                test_id UUID PRIMARY KEY,
                name TEXT,
                price DECIMAL,
                description TEXT,
                category TEXT
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id UUID PRIMARY KEY,
                booking_id UUID,
                patient_id UUID,
                test_name TEXT,
                results TEXT,
                generated_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS reports_by_booking (
                booking_id UUID PRIMARY KEY,
                report_id UUID,
                patient_id UUID,
                test_name TEXT,
                results TEXT,
                generated_at TIMESTAMP
            )
        """)

    def _prepare_statements(self):
        p = self.prepared
        p.patient_insert = self.session.prepare(
            "INSERT INTO patients (patient_id, name, phone, address, created_at) VALUES (?, ?, ?, ?, ?)"
        )
        p.patient_by_id = self.session.prepare(
            "SELECT * FROM patients WHERE patient_id = ?"
        )
        p.patient_by_phone_insert = self.session.prepare(
            "INSERT INTO patients_by_phone (phone, patient_id, name, address, created_at) VALUES (?, ?, ?, ?, ?)"
        )
        p.patient_by_phone = self.session.prepare(
            "SELECT * FROM patients_by_phone WHERE phone = ?"
        )

        p.booking_insert = self.session.prepare(
            "INSERT INTO bookings (booking_id, patient_id, patient_name, patient_phone, test_name, collection_address, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        p.booking_by_id = self.session.prepare(
            "SELECT * FROM bookings WHERE booking_id = ?"
        )
        p.bookings_by_phone_insert = self.session.prepare(
            "INSERT INTO bookings_by_phone (phone, booking_id, patient_name, test_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?)"
        )
        p.bookings_by_phone_index = self.session.prepare(
            "SELECT * FROM bookings_by_phone WHERE phone = ?"
        )

        p.doctor_insert = self.session.prepare(
            "INSERT INTO doctors (doctor_id, name, speciality, qualifications, bio) VALUES (?, ?, ?, ?, ?)"
        )
        p.doctor_by_id = self.session.prepare(
            "SELECT * FROM doctors WHERE doctor_id = ?"
        )
        p.doctor_list = self.session.prepare("SELECT * FROM doctors")

        p.test_insert = self.session.prepare(
            "INSERT INTO tests (test_id, name, price, description, category) VALUES (?, ?, ?, ?, ?)"
        )
        p.test_by_id = self.session.prepare(
            "SELECT * FROM tests WHERE test_id = ?"
        )
        p.test_list = self.session.prepare("SELECT * FROM tests")

        p.report_insert = self.session.prepare(
            "INSERT INTO reports (report_id, booking_id, patient_id, test_name, results, generated_at) VALUES (?, ?, ?, ?, ?, ?)"
        )
        p.report_by_id = self.session.prepare(
            "SELECT * FROM reports WHERE report_id = ?"
        )
        p.report_by_booking = self.session.prepare(
            "SELECT * FROM reports_by_booking WHERE booking_id = ?"
        )
        p.report_by_booking_insert = self.session.prepare(
            "INSERT INTO reports_by_booking (booking_id, report_id, patient_id, test_name, results, generated_at) VALUES (?, ?, ?, ?, ?, ?)"
        )

    # --- Patient operations ---

    def create_patient(self, name: str, phone: str, address: str) -> Patient:
        patient_id = uuid.uuid4()
        now = datetime.utcnow()
        self.session.execute(self.prepared.patient_insert, [patient_id, name, phone, address, now])
        self.session.execute(self.prepared.patient_by_phone_insert, [phone, patient_id, name, address, now])
        return Patient(patient_id=patient_id, name=name, phone=phone, address=address, created_at=str(now))

    def get_patient(self, patient_id: str) -> Patient | None:
        rows = self.session.execute(self.prepared.patient_by_id, [uuid.UUID(patient_id)])
        for row in rows:
            return Patient(patient_id=row.patient_id, name=row.name, phone=row.phone, address=row.address, created_at=str(row.created_at))
        return None

    def get_patient_by_phone(self, phone: str) -> Patient | None:
        rows = self.session.execute(self.prepared.patient_by_phone, [phone])
        for row in rows:
            return Patient(patient_id=row.patient_id, name=row.name, phone=row.phone, address=row.address, created_at=str(row.created_at))
        return None

    # --- Booking operations ---

    def create_booking(self, patient_id: str, patient_name: str, patient_phone: str, test_name: str, collection_address: str) -> Booking:
        booking_id = uuid.uuid4()
        now = datetime.utcnow()
        status = "confirmed"
        self.session.execute(self.prepared.booking_insert, [
            booking_id, uuid.UUID(patient_id), patient_name, patient_phone,
            test_name, collection_address, status, now
        ])
        self.session.execute(self.prepared.bookings_by_phone_insert, [
            patient_phone, booking_id, patient_name, test_name, status, now
        ])
        return Booking(
            booking_id=booking_id, patient_id=uuid.UUID(patient_id),
            patient_name=patient_name, patient_phone=patient_phone,
            test_name=test_name, collection_address=collection_address,
            status=status, created_at=str(now)
        )

    def get_booking(self, booking_id: str) -> Booking | None:
        rows = self.session.execute(self.prepared.booking_by_id, [uuid.UUID(booking_id)])
        for row in rows:
            return Booking(
                booking_id=row.booking_id, patient_id=row.patient_id,
                patient_name=row.patient_name, patient_phone=row.patient_phone,
                test_name=row.test_name, collection_address=row.collection_address,
                status=row.status, created_at=str(row.created_at)
            )
        return None

    def list_bookings_by_phone(self, phone: str) -> list[Booking]:
        rows = self.session.execute(self.prepared.bookings_by_phone_index, [phone])
        results = []
        for row in rows:
            results.append(Booking(
                booking_id=row.booking_id, patient_id=uuid.UUID(int=0),
                patient_name=row.patient_name, patient_phone=phone,
                test_name=row.test_name, collection_address="",
                status=row.status, created_at=str(row.created_at)
            ))
        return results

    # --- Doctor operations ---

    def create_doctor(self, name: str, speciality: str, qualifications: str, bio: str) -> Doctor:
        doctor_id = uuid.uuid4()
        self.session.execute(self.prepared.doctor_insert, [doctor_id, name, speciality, qualifications, bio])
        return Doctor(doctor_id=doctor_id, name=name, speciality=speciality, qualifications=qualifications, bio=bio)

    def list_doctors(self) -> list[Doctor]:
        rows = self.session.execute(self.prepared.doctor_list)
        return [Doctor(doctor_id=r.doctor_id, name=r.name, speciality=r.speciality, qualifications=r.qualifications, bio=r.bio) for r in rows]

    # --- Test operations ---

    def create_test(self, name: str, price: float, description: str, category: str) -> Test:
        test_id = uuid.uuid4()
        self.session.execute(self.prepared.test_insert, [test_id, name, price, description, category])
        return Test(test_id=test_id, name=name, price=price, description=description, category=category)

    def list_tests(self) -> list[Test]:
        rows = self.session.execute(self.prepared.test_list)
        return [Test(test_id=r.test_id, name=r.name, price=r.price, description=r.description, category=r.category) for r in rows]

    # --- Report operations ---

    def create_report(self, booking_id: str, patient_id: str, test_name: str, results: str) -> Report:
        report_id = uuid.uuid4()
        now = datetime.utcnow()
        self.session.execute(self.prepared.report_insert, [report_id, uuid.UUID(booking_id), uuid.UUID(patient_id), test_name, results, now])
        self.session.execute(self.prepared.report_by_booking_insert, [uuid.UUID(booking_id), report_id, uuid.UUID(patient_id), test_name, results, now])
        return Report(report_id=report_id, booking_id=uuid.UUID(booking_id), patient_id=uuid.UUID(patient_id), test_name=test_name, results=results, generated_at=str(now))

    def get_report_by_booking(self, booking_id: str) -> Report | None:
        rows = self.session.execute(self.prepared.report_by_booking, [uuid.UUID(booking_id)])
        for row in rows:
            return Report(report_id=row.report_id, booking_id=row.booking_id, patient_id=row.patient_id, test_name=row.test_name, results=row.results, generated_at=str(row.generated_at))
        return None

    def seed_doctors(self):
        existing = self.list_doctors()
        if existing:
            return
        doctors = [
            ("Dr. M.A. Majid Adil", "UROLOGIST", "MBBS, M.D, MDHM",
             "Dr. Majid Adil is a highly skilled and experienced urologist affiliated with Unicus Diagnostics. With a passion for providing exceptional patient care, Dr. Adil has gained a reputation for his expertise in diagnosing and treating various urological conditions."),
            ("Dr. Shahana Sarwar", "MANAGING DIRECTOR", "MBBS, M.D, MDHM",
             "Dr. Shahana Sarwar is a highly accomplished individual serving as the Managing Director of Unicus Diagnostics. With her exceptional leadership skills and extensive expertise in the field of diagnostics, she has propelled Unicus Diagnostics to new heights of success and recognition."),
        ]
        for name, speciality, qualifications, bio in doctors:
            self.create_doctor(name, speciality, qualifications, bio)

    def seed_tests(self):
        existing = self.list_tests()
        if existing:
            return
        tests = [
            ("Creatinine Test", 300.0, "Measures creatinine levels to assess kidney function.", "Pathology"),
            ("CBC Test", 400.0, "Complete Blood Count — evaluates overall health and detects disorders.", "Pathology"),
            ("C Reactive Protein Test", 500.0, "Measures CRP levels to detect inflammation or infection.", "Pathology"),
            ("Blood Sugar", 200.0, "Measures glucose levels in the blood for diabetes screening.", "Pathology"),
        ]
        for name, price, description, category in tests:
            self.create_test(name, price, description, category)
