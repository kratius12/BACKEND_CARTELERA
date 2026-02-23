import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import pkg from "pg";

dotenv.config();

const { Pool } = pkg;

const app = express();
app.use(cors());
app.use(express.json({ limit: "2mb" }));

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

// ──────────────────────────────────────────
//  HEALTH CHECK
// ──────────────────────────────────────────
app.get("/api/health", async (_req, res) => {
  try {
    const r = await pool.query("SELECT NOW() as now");
    res.json({ ok: true, now: r.rows[0].now });
  } catch (e) {
    console.error(e);
    res.status(500).json({ ok: false, message: "Error de base de datos" });
  }
});

// ──────────────────────────────────────────
//  PROGRAMAS PUBLICADOS
// ──────────────────────────────────────────

// GET /api/programs/current
// Retorna { id } del programa cuyas fechas contienen hoy.
// Si no existe, retorna { id: 1 }.
app.get("/api/programs/current", async (_req, res) => {
  try {
    const today = new Date().toISOString().split("T")[0]; // YYYY-MM-DD
    const r = await pool.query(
      `SELECT id FROM meeting_programs
       WHERE week_start <= $1 AND week_end >= $1
       ORDER BY week_start DESC
       LIMIT 1`,
      [today]
    );
    const id = r.rows.length ? r.rows[0].id : 1;
    res.json({ id });
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// GET /api/programs
// Lista todos los programas publicados (id, week_start, week_end, título).
app.get("/api/programs", async (_req, res) => {
  try {
    const r = await pool.query(
      `SELECT id,
              week_start,
              week_end,
              payload->>'title' AS title
       FROM meeting_programs
       ORDER BY week_start DESC`
    );
    res.json(r.rows);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// GET /api/programs/:id
// Retorna el payload completo de un programa publicado.
app.get("/api/programs/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const r = await pool.query(
      "SELECT id, week_start, week_end, payload FROM meeting_programs WHERE id = $1",
      [id]
    );

    if (!r.rows.length) return res.status(404).json({ message: "No encontrado" });

    res.json(r.rows[0].payload);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// ──────────────────────────────────────────
//  ADMINISTRACIÓN — STAGING
// ──────────────────────────────────────────

// GET /api/admin/programs/staging
// Lista todos los programas en staging.
app.get("/api/admin/programs/staging", async (_req, res) => {
  try {
    const r = await pool.query(
      `SELECT id,
              week_start,
              week_end,
              payload->>'title' AS title
       FROM meeting_programs_staging
       ORDER BY week_start DESC`
    );
    res.json(r.rows);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// GET /api/admin/programs/staging/:id
// Retorna el payload completo de un programa en staging.
app.get("/api/admin/programs/staging/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const r = await pool.query(
      "SELECT id, week_start, week_end, payload FROM meeting_programs_staging WHERE id = $1",
      [id]
    );
    if (!r.rows.length) return res.status(404).json({ message: "No encontrado en staging" });
    res.json(r.rows[0]);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// POST /api/admin/programs
// Crea un nuevo programa en staging.
// Body: { week_start, week_end, payload }
app.post("/api/admin/programs", async (req, res) => {
  const client = await pool.connect();
  try {
    const { week_start, week_end, payload } = req.body;
    if (!week_start || !week_end || !payload) {
      return res.status(400).json({ message: "Faltan campos: week_start, week_end, payload" });
    }

    await client.query("BEGIN");

    // Calcular el siguiente id: MAX(id) + 1, o 1 si la tabla está vacía
    const maxRes = await client.query(
      "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM meeting_programs_staging"
    );
    const nextId = maxRes.rows[0].next_id;

    const r = await client.query(
      `INSERT INTO meeting_programs_staging (id, week_start, week_end, payload)
       VALUES ($1, $2, $3, $4)
       RETURNING id`,
      [nextId, week_start, week_end, JSON.stringify(payload)]
    );

    await client.query("COMMIT");
    res.status(201).json({ id: r.rows[0].id, message: "Guardado en staging" });
  } catch (e) {
    await client.query("ROLLBACK");
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  } finally {
    client.release();
  }
});

// POST /api/admin/programs/:id/publish
// Mueve un programa de staging a la tabla principal.
app.post("/api/admin/programs/:id/publish", async (req, res) => {
  const client = await pool.connect();
  try {
    const id = Number(req.params.id);
    await client.query("BEGIN");

    const r = await client.query(
      "SELECT week_start, week_end, payload FROM meeting_programs_staging WHERE id = $1",
      [id]
    );

    if (!r.rows.length) {
      await client.query("ROLLBACK");
      return res.status(404).json({ message: "Programa no encontrado en staging" });
    }

    const { week_start, week_end, payload } = r.rows[0];

    // Calcular el siguiente id: MAX(id) + 1, o 1 si la tabla está vacía
    const maxRes = await client.query(
      "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM meeting_programs"
    );
    const nextId = maxRes.rows[0].next_id;

    const inserted = await client.query(
      `INSERT INTO meeting_programs (id, week_start, week_end, payload, created_at)
       VALUES ($1, $2, $3, $4, NOW())
       RETURNING id`,
      [nextId, week_start, week_end, JSON.stringify(payload)]
    );

    await client.query("DELETE FROM meeting_programs_staging WHERE id = $1", [id]);

    await client.query("COMMIT");
    res.json({ id: inserted.rows[0].id, message: "Publicado exitosamente" });
  } catch (e) {
    await client.query("ROLLBACK");
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  } finally {
    client.release();
  }
});

// PUT /api/admin/programs/staging/:id
// Actualiza un programa en staging (week_start, week_end, payload).
app.put("/api/admin/programs/staging/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const { week_start, week_end, payload } = req.body;
    if (!week_start || !week_end || !payload) {
      return res.status(400).json({ message: "Faltan campos: week_start, week_end, payload" });
    }

    const r = await pool.query(
      `UPDATE meeting_programs_staging
       SET week_start = $1, week_end = $2, payload = $3
       WHERE id = $4
       RETURNING id`,
      [week_start, week_end, JSON.stringify(payload), id]
    );

    if (!r.rows.length) {
      return res.status(404).json({ message: "Programa no encontrado en staging" });
    }

    res.json({ id: r.rows[0].id, message: "Staging actualizado" });
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// PUT /api/admin/programs/:id
// Actualiza un programa ya publicado en meeting_programs.
app.put("/api/admin/programs/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const { week_start, week_end, payload } = req.body;
    if (!week_start || !week_end || !payload) {
      return res.status(400).json({ message: "Faltan campos: week_start, week_end, payload" });
    }

    const r = await pool.query(
      `UPDATE meeting_programs
       SET week_start = $1, week_end = $2, payload = $3
       WHERE id = $4
       RETURNING id`,
      [week_start, week_end, JSON.stringify(payload), id]
    );

    if (!r.rows.length) {
      return res.status(404).json({ message: "Programa publicado no encontrado" });
    }

    res.json({ id: r.rows[0].id, message: "Programa actualizado" });
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

// ──────────────────────────────────────────
//  INICIO
// ──────────────────────────────────────────
app.listen(process.env.PORT || 3001, () => {
  console.log(`🚀 API en http://localhost:${process.env.PORT || 3001}`);
});
