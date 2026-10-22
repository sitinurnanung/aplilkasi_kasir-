import os
import csv
import io
import sqlite3
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    g,
    Response,
    send_from_directory,
)

DB_PATH = os.path.join(os.path.dirname(__file__), "toko.db")
app = Flask(__name__)
app.secret_key = "kasir-super-secret-key-2026"

@app.template_filter("ribuan")
def ribuan_filter(val):
    try:
        return f"{int(val or 0):,}"
    except (ValueError, TypeError):
        return "0"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT UNIQUE NOT NULL,
            nama TEXT NOT NULL,
            kategori TEXT DEFAULT 'Umum',
            harga INTEGER NOT NULL,
            stok INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            total INTEGER NOT NULL,
            bayar INTEGER NOT NULL,
            kembali INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS detail_transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaksi_id INTEGER NOT NULL,
            barang_id INTEGER NOT NULL,
            nama_barang TEXT NOT NULL,
            harga INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            subtotal INTEGER NOT NULL
        );
    """)

    c.execute("PRAGMA table_info(barang)")
    columns = [row[1] for row in c.fetchall()]
    if "kategori" not in columns:
        try:
            c.execute("ALTER TABLE barang ADD COLUMN kategori TEXT DEFAULT 'Umum'")
            conn.commit()
        except Exception:
            pass

    c.execute("SELECT COUNT(*) FROM barang")
    if c.fetchone()[0] == 0:
        sample = [
            ("BRG001", "Indomie Goreng Spesial", "Makanan", 3500, 120),
            ("BRG002", "Aqua Mineral 600ml", "Minuman", 4000, 95),
            ("BRG003", "Kopi Kapal Api Mantap", "Minuman", 2500, 150),
            ("BRG004", "Teh Botol Sosro Dingin", "Minuman", 5000, 60),
            ("BRG005", "Roti Tawar Serbaguna", "Makanan", 15000, 35),
            ("BRG006", "Minyak Goreng Sania 1L", "Sembako", 18500, 45),
            ("BRG007", "Gula Pasir Gulaku 1kg", "Sembako", 17000, 50),
            ("BRG008", "Beras Premium 5kg", "Sembako", 72000, 25),
            ("BRG009", "Sabun Mandi Lifebuoy", "Perawatan", 4500, 70),
            ("BRG010", "Pasta Gigi Pepsodent", "Perawatan", 8500, 40),
            ("BRG011", "Snack Chitato Sapi Panggang", "Makanan", 11000, 55),
            ("BRG012", "Susu UHT Ultra Milk 250ml", "Minuman", 7000, 65),
        ]
        c.executemany("INSERT INTO barang (kode, nama, kategori, harga, stok) VALUES (?,?,?,?,?)", sample)
    conn.commit()
    conn.close()

init_db()

def safe_barang_dict(row):
    d = dict(row)
    if "kategori" not in d or not d["kategori"]:
        d["kategori"] = "Umum"
    try:
        d["harga"] = int(d.get("harga") or 0)
    except (ValueError, TypeError):
        d["harga"] = 0
    try:
        d["stok"] = int(d.get("stok") or 0)
    except (ValueError, TypeError):
        d["stok"] = 0
    return d

@app.route("/")
def index():
    return redirect(url_for("kasir"))

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/kasir")
def kasir():
    db = get_db()
    rows = db.execute("SELECT * FROM barang").fetchall()
    kategori_set = set()
    for r in rows:
        d = safe_barang_dict(r)
        if d["kategori"]:
            kategori_set.add(d["kategori"])
    kategori_list = sorted(list(kategori_set))
    return render_template("kasir.html", active="kasir", kategori_list=kategori_list)

@app.route("/api/barang")
def api_list_barang():
    db = get_db()
    q = request.args.get("q", "").strip()
    kategori = request.args.get("kategori", "").strip()
    sql = "SELECT * FROM barang WHERE 1=1"
    params = []
    if q:
        sql += " AND (kode LIKE ? OR nama LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if kategori and kategori != "Semua":
        sql += " AND kategori = ?"
        params.append(kategori)
    sql += " ORDER BY nama ASC"
    rows = db.execute(sql, params).fetchall()
    return jsonify({"ok": True, "data": [safe_barang_dict(r) for r in rows]})


@app.route("/api/barang/<kode>")
def api_get_barang(kode):
    db = get_db()
    row = db.execute("SELECT * FROM barang WHERE kode=?", (kode,)).fetchone()
    if not row:
        return jsonify({"ok": False, "msg": "Barang tidak ditemukan"}), 404
    return jsonify({"ok": True, "data": safe_barang_dict(row)})

@app.route("/api/barang/quick-stok", methods=["POST"])
def api_quick_stok():
    data = request.get_json() or {}
    barang_id = data.get("id")
    delta = int(data.get("delta", 0))
    if not barang_id or delta == 0:
        return jsonify({"ok": False, "msg": "Data tidak valid"}), 400

    db = get_db()
    row = db.execute("SELECT stok, nama FROM barang WHERE id=?", (barang_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "msg": "Barang tidak ditemukan"}), 404

    current_stok = int(row["stok"] or 0)
    new_stok = max(0, current_stok + delta)
    db.execute("UPDATE barang SET stok=? WHERE id=?", (new_stok, barang_id))
    db.commit()
    return jsonify({"ok": True, "stok": new_stok, "nama": row["nama"]})

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json() or {}
    items = data.get("items", [])
    bayar = int(data.get("bayar", 0))
    if not items:
        return jsonify({"ok": False, "msg": "Keranjang masih kosong"}), 400

    db = get_db()
    total = 0
    checked_items = []
    for it in items:
        row = db.execute("SELECT * FROM barang WHERE id=?", (it["id"],)).fetchone()
        if not row:
            return jsonify({"ok": False, "msg": f"Barang ID {it['id']} tidak ditemukan"}), 400
        qty = int(it.get("qty", 1))
        harga = int(row["harga"] or 0)
        stok = int(row["stok"] or 0)
        if qty <= 0:
            return jsonify({"ok": False, "msg": f"Qty tidak valid untuk {row['nama']}"}), 400
        if qty > stok:
            return jsonify({"ok": False, "msg": f"Stok {row['nama']} tidak mencukupi (Tersisa: {stok})"}), 400
        subtotal = harga * qty
        total += subtotal
        checked_items.append({
            "id": row["id"],
            "kode": row["kode"],
            "nama": row["nama"],
            "harga": harga,
            "qty": qty,
            "subtotal": subtotal,
        })

    if bayar < total:
        return jsonify({"ok": False, "msg": f"Uang bayar kurang! Total: Rp {total:,}, Bayar: Rp {bayar:,}"}), 400

    kembali = bayar - total
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        "INSERT INTO transaksi (tanggal,total,bayar,kembali) VALUES (?,?,?,?)",
        (now, total, bayar, kembali),
    )
    trans_id = cur.lastrowid
    for it in checked_items:
        db.execute(
            """INSERT INTO detail_transaksi
               (transaksi_id,barang_id,nama_barang,harga,qty,subtotal)
               VALUES (?,?,?,?,?,?)""",
            (trans_id, it["id"], it["nama"], it["harga"], it["qty"], it["subtotal"]),
        )
        db.execute("UPDATE barang SET stok=stok-? WHERE id=?", (it["qty"], it["id"]))
    db.commit()

    return jsonify({
        "ok": True,
        "trans_id": trans_id,
        "tanggal": now,
        "total": total,
        "bayar": bayar,
        "kembali": kembali,
        "items": checked_items,
    })

@app.route("/struk/<int:trans_id>")
def struk(trans_id):
    db = get_db()
    trx = db.execute("SELECT * FROM transaksi WHERE id=?", (trans_id,)).fetchone()
    if not trx:
        flash("Transaksi tidak ditemukan", "danger")
        return redirect(url_for("kasir"))
    detail = db.execute(
        "SELECT * FROM detail_transaksi WHERE transaksi_id=?", (trans_id,)
    ).fetchall()
    return render_template("struk.html", trx=trx, detail=detail)

@app.route("/barang")
def barang():
    db = get_db()
    q = request.args.get("q", "").strip()
    kategori = request.args.get("kategori", "").strip()
    filter_stok = request.args.get("stok", "").strip()

    all_rows = db.execute("SELECT * FROM barang").fetchall()
    all_barang = [safe_barang_dict(r) for r in all_rows]

    total_produk = len(all_barang)
    total_stok = sum(b["stok"] for b in all_barang)
    total_nilai_aset = sum(b["harga"] * b["stok"] for b in all_barang)
    stok_menipis_count = sum(1 for b in all_barang if 0 < b["stok"] <= 10)
    stok_habis_count = sum(1 for b in all_barang if b["stok"] <= 0)

    stats = {
        "total_produk": total_produk,
        "total_stok": total_stok,
        "total_nilai_aset": total_nilai_aset,
        "stok_menipis": stok_menipis_count,
        "stok_habis": stok_habis_count,
    }

    kategori_set = set(b["kategori"] for b in all_barang if b["kategori"])
    kategori_list = sorted(list(kategori_set))

    sql = "SELECT * FROM barang WHERE 1=1"
    params = []
    if q:
        sql += " AND (kode LIKE ? OR nama LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    if kategori and kategori != "Semua":
        sql += " AND kategori = ?"
        params.append(kategori)
    if filter_stok == "habis":
        sql += " AND stok <= 0"
    elif filter_stok == "kritis":
        sql += " AND stok > 0 AND stok <= 5"
    elif filter_stok == "menipis":
        sql += " AND stok > 0 AND stok <= 10"

    sql += " ORDER BY nama ASC"
    filtered_rows = db.execute(sql, params).fetchall()
    barang_list = [safe_barang_dict(r) for r in filtered_rows]

    return render_template(
        "barang.html",
        active="barang",
        barang=barang_list,
        q=q,
        kategori=kategori,
        filter_stok=filter_stok,
        kategori_list=kategori_list,
        stats=stats,
    )

@app.route("/barang/tambah", methods=["POST"])
def barang_tambah():
    kode = request.form["kode"].strip().upper()
    nama = request.form["nama"].strip()
    kategori = request.form.get("kategori", "Umum").strip() or "Umum"
    try:
        harga = int(request.form.get("harga", 0))
    except (ValueError, TypeError):
        harga = 0
    try:
        stok = int(request.form.get("stok", 0))
    except (ValueError, TypeError):
        stok = 0

    if not kode or not nama:
        flash("Kode dan Nama barang wajib diisi!", "danger")
        return redirect(url_for("barang"))

    try:
        db = get_db()
        db.execute(
            "INSERT INTO barang (kode,nama,kategori,harga,stok) VALUES (?,?,?,?,?)",
            (kode, nama, kategori, harga, stok),
        )
        db.commit()
        flash(f'Barang "{nama}" berhasil ditambahkan!', "success")
    except sqlite3.IntegrityError:
        flash(f'Kode barang "{kode}" sudah dipakai! Gunakan kode lain.', "danger")
    return redirect(url_for("barang"))

@app.route("/barang/edit/<int:id_>", methods=["POST"])
def barang_edit(id_):
    kode = request.form["kode"].strip().upper()
    nama = request.form["nama"].strip()
    kategori = request.form.get("kategori", "Umum").strip() or "Umum"
    try:
        harga = int(request.form.get("harga", 0))
    except (ValueError, TypeError):
        harga = 0
    try:
        stok = int(request.form.get("stok", 0))
    except (ValueError, TypeError):
        stok = 0

    try:
        db = get_db()
        db.execute(
            "UPDATE barang SET kode=?,nama=?,kategori=?,harga=?,stok=? WHERE id=?",
            (kode, nama, kategori, harga, stok, id_),
        )
        db.commit()
        flash(f'Data barang "{nama}" berhasil diperbarui!', "success")
    except sqlite3.IntegrityError:
        flash(f'Kode barang "{kode}" sudah dipakai oleh produk lain!', "danger")
    return redirect(url_for("barang"))

@app.route("/barang/hapus/<int:id_>", methods=["POST"])
def barang_hapus(id_):
    db = get_db()
    row = db.execute("SELECT nama FROM barang WHERE id=?", (id_,)).fetchone()
    nama = row["nama"] if row else "Barang"
    db.execute("DELETE FROM barang WHERE id=?", (id_,))
    db.commit()
    flash(f'Barang "{nama}" berhasil dihapus!', "success")
    return redirect(url_for("barang"))

@app.route("/laporan")
def laporan():
    db = get_db()
    tgl1 = request.args.get("tgl1", "").strip()
    tgl2 = request.args.get("tgl2", "").strip()

    if tgl1 and tgl2:
        rows = db.execute(
            """SELECT * FROM transaksi
               WHERE date(tanggal) BETWEEN ? AND ? ORDER BY id DESC""",
            (tgl1, tgl2),
        ).fetchall()
    elif tgl1:
        rows = db.execute(
            """SELECT * FROM transaksi
               WHERE date(tanggal) >= ? ORDER BY id DESC""",
            (tgl1,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM transaksi ORDER BY id DESC").fetchall()

    total_omset = sum(int(r["total"] or 0) for r in rows)
    total_trx = len(rows)
    rata_rata = int(total_omset / total_trx) if total_trx > 0 else 0

    top_items_sql = """
        SELECT nama_barang, SUM(qty) as total_qty, SUM(subtotal) as total_nominal
        FROM detail_transaksi
    """
    if tgl1 and tgl2:
        top_items_sql += """
            JOIN transaksi ON detail_transaksi.transaksi_id = transaksi.id
            WHERE date(transaksi.tanggal) BETWEEN ? AND ?
        """
        top_items = db.execute(
            top_items_sql + " GROUP BY nama_barang ORDER BY total_qty DESC LIMIT 5",
            (tgl1, tgl2),
        ).fetchall()
    else:
        top_items = db.execute(
            top_items_sql + " GROUP BY nama_barang ORDER BY total_qty DESC LIMIT 5"
        ).fetchall()

    return render_template(
        "laporan.html",
        active="laporan",
        transaksi=rows,
        total=total_omset,
        total_trx=total_trx,
        rata_rata=rata_rata,
        top_items=top_items,
        tgl1=tgl1,
        tgl2=tgl2,
    )

@app.route("/laporan/export-csv")
def laporan_export_csv():
    db = get_db()
    tgl1 = request.args.get("tgl1", "").strip()
    tgl2 = request.args.get("tgl2", "").strip()

    if tgl1 and tgl2:
        rows = db.execute(
            """SELECT * FROM transaksi
               WHERE date(tanggal) BETWEEN ? AND ? ORDER BY id ASC""",
            (tgl1, tgl2),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM transaksi ORDER BY id ASC").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID Transaksi", "Tanggal & Waktu", "Total Belanja (Rp)", "Jumlah Bayar (Rp)", "Kembalian (Rp)"])

    for r in rows:
        writer.writerow([r["id"], r["tanggal"], r["total"], r["bayar"], r["kembali"]])

    filename = f"laporan_penjualan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )

@app.route("/laporan/<int:trans_id>")
def laporan_detail(trans_id):
    db = get_db()
    trx = db.execute("SELECT * FROM transaksi WHERE id=?", (trans_id,)).fetchone()
    detail = db.execute(
        "SELECT * FROM detail_transaksi WHERE transaksi_id=?", (trans_id,)
    ).fetchall()
    return render_template("struk.html", trx=trx, detail=detail, from_laporan=True)

if __name__ == "__main__":
    print("=" * 60)
    print("  APLIKASI KASIR & INVENTARIS TOKO (RESPONSIVE POS)")
    print("=" * 60)
    print("  Desktop & Mobile: http://127.0.0.1:5000")
    print("  Untuk mode Desktop Window, jalankan: python run_desktop.py")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)