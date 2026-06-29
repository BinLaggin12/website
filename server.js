const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = 3000;
const DATA_FILE = path.join(__dirname, "data.json");
const MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".png": "image/png",
  ".webp": "image/webp",
};

// --- Data storage ---

function loadData() {
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
  } catch {
    return { patients: [], bookings: [], reports: [], doctors: [], tests: [] };
  }
}

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

function uid() {
  return "xxxx-xxxx-xxxx".replace(/x/g, () =>
    Math.floor(Math.random() * 16).toString(16)
  );
}

// --- Seed data ---

function seed() {
  const data = loadData();
  if (data.doctors.length === 0) {
    data.doctors = [
      {
        doctor_id: uid(),
        name: "Dr. M.A. Majid Adil",
        speciality: "UROLOGIST",
        qualifications: "MBBS, M.D, MDHM",
        bio: "Dr. Majid Adil is a highly skilled and experienced urologist affiliated with Unicus Diagnostics. With a passion for providing exceptional patient care, Dr. Adil has gained a reputation for his expertise in diagnosing and treating various urological conditions.",
      },
      {
        doctor_id: uid(),
        name: "Dr. Shahana Sarwar",
        speciality: "MANAGING DIRECTOR",
        qualifications: "MBBS, M.D, MDHM",
        bio: "Dr. Shahana Sarwar is a highly accomplished individual serving as the Managing Director of Unicus Diagnostics. With her exceptional leadership skills and extensive expertise in the field of diagnostics, she has propelled Unicus Diagnostics to new heights of success and recognition.",
      },
    ];
  }
  if (data.tests.length === 0) {
    data.tests = [
      { test_id: uid(), name: "Creatinine Test", price: 300, description: "Measures creatinine levels to assess kidney function.", category: "Pathology" },
      { test_id: uid(), name: "CBC Test", price: 400, description: "Complete Blood Count — evaluates overall health and detects disorders.", category: "Pathology" },
      { test_id: uid(), name: "C Reactive Protein Test", price: 500, description: "Measures CRP levels to detect inflammation or infection.", category: "Pathology" },
      { test_id: uid(), name: "Blood Sugar", price: 200, description: "Measures glucose levels in the blood for diabetes screening.", category: "Pathology" },
    ];
  }
  saveData(data);
}
seed();

// --- API handlers ---

function apiRoutes(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = url.pathname;
  const method = req.method;

  const send = (status, data) => {
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(data));
  };

  const body = (cb) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => cb(JSON.parse(raw)));
  };

  // --- Doctors ---
  if (pathname === "/api/doctors" && method === "GET") {
    const data = loadData();
    send(200, data.doctors);
  }

  // --- Tests ---
  else if (pathname === "/api/tests" && method === "GET") {
    const data = loadData();
    send(200, data.tests);
  }

  // --- Patient by phone ---
  else if (pathname.startsWith("/api/patient/phone/") && method === "GET") {
    const phone = decodeURIComponent(pathname.split("/api/patient/phone/")[1]);
    const data = loadData();
    const patient = data.patients.find((p) => p.phone === phone);
    if (!patient) return send(404, { error: "Patient not found" });
    send(200, patient);
  }

  // --- Patient by ID ---
  else if (pathname.startsWith("/api/patient/") && method === "GET") {
    const id = pathname.split("/api/patient/")[1];
    const data = loadData();
    const patient = data.patients.find((p) => p.patient_id === id);
    if (!patient) return send(404, { error: "Patient not found" });
    send(200, patient);
  }

  // --- Create patient ---
  else if (pathname === "/api/patient/create" && method === "POST") {
    body((b) => {
      const data = loadData();
      const existing = data.patients.find((p) => p.phone === b.phone);
      if (existing) return send(200, existing);
      const patient = {
        patient_id: uid(),
        name: b.name,
        phone: b.phone,
        address: b.address || "",
        created_at: new Date().toISOString(),
      };
      data.patients.push(patient);
      saveData(data);
      send(200, patient);
    });
  }

  // --- Create booking ---
  else if (pathname === "/api/booking/create" && method === "POST") {
    body((b) => {
      const data = loadData();
      let patient = data.patients.find((p) => p.phone === b.patient_phone);
      if (!patient) {
        patient = {
          patient_id: uid(),
          name: b.patient_name,
          phone: b.patient_phone,
          address: b.collection_address,
          created_at: new Date().toISOString(),
        };
        data.patients.push(patient);
      }
      const booking = {
        booking_id: uid(),
        patient_id: patient.patient_id,
        patient_name: b.patient_name,
        patient_phone: b.patient_phone,
        test_name: b.test_name,
        collection_address: b.collection_address,
        status: "confirmed",
        created_at: new Date().toISOString(),
      };
      data.bookings.push(booking);
      saveData(data);
      send(200, booking);
    });
  }

  // --- Get booking by ID ---
  else if (pathname.startsWith("/api/booking/") && method === "GET") {
    const id = pathname.split("/api/booking/")[1];
    const data = loadData();
    const booking = data.bookings.find((b) => b.booking_id === id);
    if (!booking) return send(404, { error: "Booking not found" });
    send(200, booking);
  }

  // --- Bookings by phone ---
  else if (pathname.startsWith("/api/bookings/") && method === "GET") {
    const phone = decodeURIComponent(pathname.split("/api/bookings/")[1]);
    const data = loadData();
    const bookings = data.bookings.filter((b) => b.patient_phone === phone);
    send(200, bookings);
  }

  // --- Create report ---
  else if (pathname === "/api/report/create" && method === "POST") {
    body((b) => {
      const data = loadData();
      const booking = data.bookings.find((bk) => bk.booking_id === b.booking_id);
      if (!booking) return send(404, { error: "Booking not found" });
      const report = {
        report_id: uid(),
        booking_id: b.booking_id,
        patient_id: booking.patient_id,
        test_name: booking.test_name,
        results: b.results,
        generated_at: new Date().toISOString(),
      };
      data.reports.push(report);
      saveData(data);
      send(200, report);
    });
  }

  // --- Get report by booking ID ---
  else if (pathname.startsWith("/api/report/") && method === "GET") {
    const bookingId = pathname.split("/api/report/")[1];
    const data = loadData();
    const report = data.reports.find((r) => r.booking_id === bookingId);
    if (!report) return send(404, { error: "Report not found for this booking" });
    send(200, report);
  }

  // --- Seed ---
  else if (pathname === "/api/seed" && method === "POST") {
    seed();
    send(200, { status: "ok", message: "Doctors and tests seeded" });
  }

  else {
    send(404, { error: "API route not found" });
  }
}

// --- HTTP server ---

http
  .createServer((req, res) => {
    if (req.url.startsWith("/api/")) {
      return apiRoutes(req, res);
    }

    let filePath = req.url === "/" ? "/index.html" : decodeURIComponent(req.url);
    filePath = path.join(__dirname, filePath);
    const ext = path.extname(filePath);

    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end("Not found");
      } else {
        res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
        res.end(data);
      }
    });
  })
  .listen(PORT, () => {
    console.log(`Unicus Diagnostics server running at http://localhost:${PORT}`);
  });
