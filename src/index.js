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

// Health check
app.get("/api/health", async (_req, res) => {
  const r = await pool.query("SELECT NOW() as now");
  res.json({ ok: true, now: r.rows[0].now });
});

// GET program by id
app.get("/api/programs/:id", async (req, res) => {
  try {
    const id = Number(req.params.id);
    const r = await pool.query(
      "SELECT id, week_start, week_end, payload FROM meeting_programs WHERE id = $1",
      [id]
    );

    if (!r.rows.length) return res.status(404).json({ message: "No encontrado" });

    // devolvemos el JSON (payload) directamente
    res.json(r.rows[0].payload);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: "Error interno" });
  }
});

app.listen(process.env.PORT || 3001, () => {
  console.log(`🚀 API en http://localhost:${process.env.PORT || 3001}`);
});
