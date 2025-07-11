from flask import Flask, request, render_template, session, redirect, url_for
import ollama
from sentence_transformers import SentenceTransformer
from psycopg2.extensions import register_adapter, AsIs
import numpy as np
from flask_session import Session
from huggingface_hub import InferenceClient   # <— client HF
from dotenv import load_dotenv
import os, psycopg2, urllib.parse as up

load_dotenv() 
app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


HF_TOKEN = os.getenv("HF_API_TOKEN")  

hf_client = InferenceClient(
    model="meta-llama/Meta-Llama-3-8B-Instruct",
    token=HF_TOKEN
)




#-------------------------------------- Embedder model --------------------------------------
embedder = SentenceTransformer("BAAI/bge-m3")




#-------------------------------------- Database connect --------------------------------------
# def get_db_conn():
#     return psycopg2.connect(
#         dbname="postgres",
#         user="admin",
#         password="1234",
#         host="localhost",
#         port="5432"
#     )

USER     = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST     = os.getenv("HOST")
PORT     = os.getenv("PORT", "6543")
DBNAME   = os.getenv("DBNAME", "postgres")

def get_db_conn():
# Connect to the database
    conn = psycopg2.connect(
        user=USER,
        password=PASSWORD,
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        sslmode="require"      
    )
    print("Connection successful!")
    return conn
    
#--------------------------------------  Chat Bot --------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        user_message = request.form["message"].strip()
        # print(" [DEBUG] Received user_message:", user_message)

        if not user_message:
            session["latest_reply"] = " กรุณากรอกข้อความ"
            session["latest_user_message"] = ""
            return redirect(url_for("index"))

        context = query(user_message)
        # print(" [DEBUG] Retrieved context:", context)

        session["chat_history"].append({"role": "user", "content": user_message})
        session["chat_history"] = session["chat_history"][-10:]
        
        # เรียกใช้ model llama3:8b
        
        # try:
        #     res = ollama.chat(
        #         model="llama3:8b",
        #         messages=[{"role": "system", "content": f"ข้อมูลอ้างอิง: {context}"}] + session["chat_history"]
        #     )
        #     reply = res["message"]["content"]
        # except Exception as e:
        #     print("❌ [ERROR] ollama.chat failed:", e)
        #     reply = "⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ AI"
        try:
            # 1) รวม system + history เป็น list ตามสเปก HF
            messages = [{"role": "system",
                        "content": f"ข้อมูลอ้างอิง: {context}"}] \
                    + session["chat_history"]

            # 2) เรียก Hugging-Face Inference
            completion = hf_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=512
            )
            reply = completion.choices[0].message.content

        except Exception as e:
            print("❌ [ERROR] HF chat failed:", e)
            reply = "⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ AI"
        print(" [DEBUG] Bot replied:", reply)

        session["chat_history"].append({"role": "assistant", "content": reply})
        session["chat_history"] = session["chat_history"][-10:]
        session["latest_reply"] = reply
        session["latest_user_message"] = user_message
        session.modified = True

        return redirect(url_for("index"))

    # ดึงข้อมูลสินค้าทั้งหมดจากฐานข้อมูล สำหรับแสดงในตาราง
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT product_name, product_detail, product_price, product_quantity FROM products")
    products = cur.fetchall()
    cur.close()
    conn.close()

    reply = session.pop("latest_reply", "")
    user_message = session.pop("latest_user_message", "")

    return render_template(
        "index.html",
        reply=reply,
        user_message=user_message,
        history=session.get("chat_history", []),
        products=products  #  ส่งเข้า index.html
    )


#-------------------------------------- Reset Chat --------------------------------------
@app.route("/reset", methods=["POST"])
def reset_chat():
    session.clear()  # ล้างทุก key
    # print(" [DEBUG] Session cleared")
    return redirect("/")  # กลับไปหน้าหลักแบบ clean




#-------------------------------------- Query --------------------------------------
def query(user_message, k=5):
    question_embedding = embedder.encode(user_message).tolist()
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT product_name, product_detail, product_price, product_quantity,product_category, embedding <=> %s::vector AS similarity
        FROM products
        ORDER BY similarity ASC
        LIMIT %s;
    """, (question_embedding, k))

    results = cur.fetchall()
    cur.close()
    conn.close()

    if results:
        response = ""
        for name, detail, price, qty, product_category , _   in results:
            response += f"สินค้า: {name}\nรายละเอียด: {detail}\nราคา: {price} บาท\nคงเหลือ: {qty} ชิ้น\n ประเภท{product_category}\n"
        return response.strip()
    else:
        return "ไม่พบข้อมูลที่เกี่ยวข้อง"

#-------------------------------------- Insert product --------------------------------------
@app.route("/add", methods=["POST"])
def add_data():
    product_name = request.form["product"]
    detail = request.form["detail"]
    price = float(request.form["price"])
    quantity = int(request.form["quantity"])
    product_category = request.form["category"]

    full_text = f"ชื่อสินค้า {product_name}. รายละเอียดสินค้า {detail}.ราคา {price} บาท .มีจำนวนหรือคงเหลือ {quantity} หน่วยหรือชิ้นหรืออัน.ประเภท {product_category }"
    embedding = embedder.encode(full_text).tolist()

    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (product_name, product_detail, product_price, product_quantity,product_category, embedding)
        VALUES (%s, %s, %s, %s, %s,%s)
    """, (product_name, detail, price, quantity,product_category , embedding))
    conn.commit()
    cur.close()
    conn.close()

    return "✅ บันทึกสินค้าสำเร็จ"




# สำหรับ add ข้อมูลหลายรายการ
def add_sample_products():
    sample_products = [
    ("แล็ปท็อป Dell Inspiron", "แล็ปท็อปใช้งานทั่วไป หน้าจอ 15.6 นิ้ว RAM 8GB SSD 256GB", 18500, 25, "โน้ตบุ๊ค/คอมพิวเตอร์"),
    ("สมาร์ทโฟน Samsung Galaxy A15", "จอใหญ่ แบตอึด กล้อง 50MP ใช้งานทั่วไปลื่นไหล", 7990, 35, "อุปกรณ์พกพา/มือถือ"),
    ("หูฟังบลูทูธ Sony WH-CH520", "เสียงดี เบสแน่น ใช้งานได้ต่อเนื่อง 50 ชั่วโมง", 1890, 15, "อุปกรณ์พกพา/มือถือ"),
    ("จอมอนิเตอร์ LG 24 นิ้ว", "จอ IPS Full HD รองรับ HDMI และ VGA", 3490, 18, "อุปกรณ์ต่อพ่วง"),
    ("เครื่องพิมพ์ Canon G2020", "Print Scan Copy พร้อมแทงค์หมึกแท้ ประหยัดหมึก", 4990, 12, "อุปกรณ์สำนักงาน"),
    ("คีย์บอร์ด Mechanical Redragon", "มีไฟ RGB เสียงคลิกสนุก ปุ่มเด้งไว", 1190, 50, "อุปกรณ์ต่อพ่วง"),
    ("เมาส์ Logitech G102", "เซ็นเซอร์แม่นยำ DPI สูงสุด 8000 เหมาะกับเกมเมอร์", 590, 40, "อุปกรณ์ต่อพ่วง"),
    ("แฟลชไดร์ฟ Kingston 64GB", "ความเร็วสูง USB 3.2 ขนาดกะทัดรัด", 329, 100, "อุปกรณ์สำนักงาน"),
    ("ปลั๊กไฟ Anitech 4 ช่อง", "ปลอดภัย มีสวิตช์ควบคุมแต่ละช่อง สายยาว 3 เมตร", 459, 75, "อุปกรณ์ต่อพ่วง"),
    ("เก้าอี้เกมมิ่ง Nubwo", "เบาะหนังเทียมนุ่ม รองรับสรีระได้ดี ปรับเอนได้", 4590, 10, "อุปกรณ์สำนักงาน"),
    ("พาวเวอร์แบงค์ Eloop 20000mAh", "รองรับชาร์จเร็ว Type-C และ QC3.0", 799, 45, "อุปกรณ์พกพา/มือถือ"),
    ("สายชาร์จ Remax 3-in-1", "Lightning / Type-C / MicroUSB สายถักยาว 1.2 เมตร", 189, 60, "อุปกรณ์ต่อพ่วง"),
    ("ลำโพง Bluetooth JBL GO3", "พกพาง่าย เสียงดี กันน้ำ IP67", 1290, 20, "อุปกรณ์พกพา/มือถือ"),
    ("กล้องวงจรปิด Xiaomi", "เชื่อมต่อ Wi-Fi ดูผ่านมือถือ บันทึกลง MicroSD", 990, 30, "เครื่องใช้ไฟฟ้าในบ้าน"),
    ("ฮาร์ดดิสก์พกพา WD 1TB", "สำหรับสำรองข้อมูล USB 3.0", 1590, 25, "อุปกรณ์สำนักงาน"),
    ("โน้ตบุ๊ก HP Ryzen 5", "RAM 16GB SSD 512GB ใช้งานลื่น พร้อม Windows 11", 23900, 5, "โน้ตบุ๊ค/คอมพิวเตอร์"),
    ("เครื่องฟอกอากาศ Sharp", "ระบบ Plasmacluster ฟอกฝุ่น PM2.5 ได้ดี", 6990, 8, "เครื่องใช้ไฟฟ้าในบ้าน"),
    ("เครื่องชงกาแฟ Nespresso", "สำหรับแคปซูล ใช้งานง่าย รวดเร็ว", 3690, 12, "เครื่องใช้ไฟฟ้าในบ้าน"),
    ("ไมโครเวฟ Toshiba", "23 ลิตร ระบบดิจิตอล ตั้งเวลาอุ่นอาหาร", 2990, 14, "เครื่องใช้ไฟฟ้าในบ้าน"),
    ("เครื่องดูดฝุ่น Dyson V8", "ไร้สาย แรงดูดดี สำหรับบ้านมีสัตว์เลี้ยง", 11500, 7, "เครื่องใช้ไฟฟ้าในบ้าน"),
]


    conn = get_db_conn()
    cur = conn.cursor()

    for product_name, detail, price, quantity, product_category in sample_products :
        full_text = f"ชื่อสินค้า {product_name}. รายละเอียดสินค้า {detail}.ราคา {price} บาท .มีจำนวนหรือคงเหลือ {quantity} หน่วยหรือชิ้นหรืออัน .ประเภทสินค้า {product_category}"

        embedding = embedder.encode(full_text).tolist()

        cur.execute("""
            INSERT INTO products (product_name, product_detail, product_price, product_quantity,product_category , embedding)
            VALUES (%s, %s, %s, %s, %s,%s)
        """, (product_name, detail, price, quantity,product_category, embedding))

    conn.commit()
    cur.close()
    conn.close()

    return "✅ เพิ่มข้อมูลทดสอบ 20 รายการเรียบร้อยแล้ว"

@app.route("/load-sample")
def load_sample():
    msg = add_sample_products()
    return msg








if __name__ == "__main__":

    app.run(debug=True)
