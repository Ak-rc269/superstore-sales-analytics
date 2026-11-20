# Superstore Sales & Profit Analytics

โปรเจกต์ Data Pipeline สำหรับวิเคราะห์ยอดขายและกำไรจาก **Sample Superstore** โดยรัน Python บนเครื่องและ PostgreSQL บน Docker แล้วเผยแพร่ข้อมูลไป Google Sheets เพื่อสร้าง Dashboard ใน Data Studio

## 1. ขอบเขตและสถานะงาน

โค้ดจัดเตรียมครบสำหรับ `ingest → transform → publish` มีข้อมูลต้นฉบับ คู่มือ และค่าอ้างอิงจากการคำนวณ CSV จริง ส่วน PostgreSQL บน Docker, การเขียน Google Sheets และ Dashboard ออนไลน์ต้องรันและตั้งค่าในบัญชีของผู้ใช้ ยังไม่ได้ทดสอบการเชื่อมบริการเหล่านี้จริงในสภาพแวดล้อมที่สร้างไฟล์ชุดนี้

ทดสอบการแปลงข้อมูลและการเตรียมคำขอส่ง Sheets แบบจำลองผ่าน **11 tests** ด้วย Python 3.12.14 / pandas 2.2.3 รวมการเทียบยอดด้วย Decimal, การเก็บแถวขาดทุน, การนับ Order, วันที่ และรหัสไปรษณีย์ คำสั่งทดสอบคือ `python -m unittest discover -s tests -v` โดยการทดสอบนี้ไม่เชื่อม PostgreSQL หรือ Google API จริง

| ขั้นตอน | โปรแกรม | ผลลัพธ์ |
|---|---|---|
| อ่าน CSV | `ingest.py` | `raw_data.superstore` ใน PostgreSQL |
| ทำความสะอาดและสรุป | `transform.py` | ตารางรายละเอียดและตารางสรุปใน `production` |
| เผยแพร่ | `publish.py` | แท็บ `dashboard_data` ใน Google Sheets |
| รันต่อเนื่อง | `run_pipeline.py` | เรียกทั้งสามขั้นตอนตามลำดับและหยุดเมื่อขั้นตอนใดล้มเหลว |
| แสดงผล | Data Studio | กราฟ 5 ข้อและตัวกรองจาก Google Sheets |

สคริปต์อ่าน CSV ที่ดาวน์โหลดจาก Kaggle ไว้แล้ว ไม่ได้ดาวน์โหลด Dataset ใหม่ทุกครั้งที่รัน การรันซ้ำแทนที่ตารางของโปรเจกต์และข้อมูลในแท็บปลายทาง ไม่เพิ่มชุดเดิมซ้ำด้วยการ append

## 2. ชุดข้อมูลและค่าอ้างอิง

แหล่งข้อมูล: [Superstore Dataset บน Kaggle](https://www.kaggle.com/datasets/vivek468/superstore-dataset-final)

ไฟล์ที่ผู้ใช้ส่งมาคือ `Sample - Superstore.csv` ภายในแพ็กเกจนี้เก็บสำเนาเนื้อหาเดิมไว้ที่ `data/raw/superstore.csv` หากนำโค้ดมาจาก GitHub ให้ดาวน์โหลด CSV จากลิงก์ข้างต้นแล้ววางที่ตำแหน่งนี้เอง

| รายการตรวจ | ค่าที่คำนวณจาก CSV |
|---|---:|
| จำนวนแถว / คอลัมน์ต้นทาง | 9,994 / 21 |
| คำสั่งซื้อที่ไม่ซ้ำ | 5,009 |
| ลูกค้าที่ไม่ซ้ำ | 793 |
| วันที่สั่งซื้อ | 3 มกราคม 2014 ถึง 30 ธันวาคม 2017 |
| ยอดขายรวม | 2,297,200.8603 |
| กำไรรวม | 286,397.0217 |
| อัตรากำไรรวม | 12.47% |

ตัวเลขยอดขายและกำไรใช้หน่วยตามไฟล์ต้นทาง ซึ่งไม่มีคอลัมน์ระบุสกุลเงิน จึงไม่แปลงหรือระบุว่าเป็นบาท หนึ่งแถวเป็น **รายการสินค้าในคำสั่งซื้อ** จำนวนแถวจึงไม่เท่ากับจำนวน Order

การทำความสะอาดที่ใช้กับไฟล์จริง:

- อ่าน encoding `cp1252` และรักษารหัสลูกค้า สินค้า คำสั่งซื้อ และรหัสไปรษณีย์เป็นข้อความ
- แปลงวันที่ด้วย `%m/%d/%Y` และแปลงยอดขาย กำไร จำนวน และส่วนลดเป็นตัวเลข
- จัดช่องว่างและ NBSP ในข้อความ โดยไฟล์จริงพบ NBSP ใน 225 แถว
- เติมศูนย์ด้านหน้ารหัสไปรษณีย์สหรัฐให้ครบ 5 หลัก จำนวน 438 แถว
- ไม่พบค่าว่างและแถวซ้ำทั้ง 21 คอลัมน์ในไฟล์ต้นฉบับ จึงไม่มีการสร้างค่าว่างหรือลบข้อมูลเพื่อสาธิต
- เก็บกำไรติดลบไว้เพราะเป็นข้อมูลขาดทุน เก็บ Row ID `3406` และ `3407` แม้ข้อมูลคอลัมน์อื่นตรงกัน เพราะยังยืนยันไม่ได้ว่าเป็นรายการซ้ำจริง

## 3. ไฟล์ที่ใช้

| ไฟล์ / โฟลเดอร์ | หน้าที่ |
|---|---|
| `config.py` | อ่าน `.env` และตั้งค่าฐานข้อมูล/ไฟล์/Google Sheets |
| `ingest.py`, `transform.py`, `publish.py`, `run_pipeline.py` | โปรแกรมหลักตามโจทย์ |
| `docker-compose.yml` | PostgreSQL 16 พร้อม volume และ healthcheck |
| `.env.example` | ตัวอย่างการตั้งค่าที่คัดลอกเป็น `.env` บนเครื่อง |
| `requirements.txt` | Python dependencies |
| `.gitignore` | กัน credentials, `.env`, virtual environment และ CSV ดิบออกจาก Git |
| `data/raw/superstore.csv` | CSV ต้นฉบับสำหรับเครื่องผู้ใช้ |
| `reference_outputs/` | ผลคำนวณจาก CSV สำหรับเทียบผล ไม่ใช่หลักฐานว่าส่งข้อมูลขึ้นคลาวด์แล้ว |
| `outputs/` | CSV และ `data_quality.json` ที่สร้างเมื่อรัน transform บนเครื่อง |
| [docs/dashboard_guide.md](docs/dashboard_guide.md) | การตั้ง Data Source, metric, กราฟ 5 ข้อ และการแชร์รายงาน |
| [docs/project_report_draft.md](docs/project_report_draft.md) | ร่างรายงานพร้อมผลวิเคราะห์จริง รอเติมหลักฐานการรันและลิงก์ |
| `docs/dashboard_reference.png` | ภาพกราฟอ้างอิงที่คำนวณจาก CSV เพื่อช่วยจัดหน้า Data Studio |
| `sql/validation_queries.sql` | คำสั่งตรวจยอดและจำนวนแถวในฐานข้อมูลหลังรันจริง |
| `tests/test_data_pipeline.py` | การทดสอบข้อมูลและคำขอส่ง Sheets แบบไม่เชื่อมบริการ |

## 4. เริ่มรันบน Windows PowerShell

### 4.1 ตรวจเครื่องมือ

ใช้ Python **3.11 หรือ 3.12** และเปิด Docker Desktop ให้พร้อมใช้งาน จากนั้นเปิด PowerShell ในโฟลเดอร์ที่มี `run_pipeline.py`

```powershell
py --list
docker --version
docker compose version
docker info
```

`docker info` ต้องติดต่อ Docker Engine ได้ ถ้า `py` หรือ `docker` ไม่พบคำสั่ง ให้ติดตั้งหรือแก้ PATH ก่อนขั้นตอนถัดไป

### 4.2 สร้าง Python environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

ถ้ามี Python 3.11 ให้เปลี่ยน `-3.12` เป็น `-3.11` หรือใช้ `py -m venv .venv` เมื่อ Python เริ่มต้นเป็น 3.11/3.12 คำสั่งในคู่มือนี้เรียก Python ใน `.venv` โดยตรง จึงไม่ต้องแก้ Execution Policy เพื่อ activate environment

### 4.3 ตั้งค่าโปรเจกต์ครั้งแรก

```powershell
Copy-Item .env.example .env
notepad .env
```

คัดลอกเฉพาะครั้งแรก เพื่อไม่ทับการตั้งค่าที่มีอยู่ เปลี่ยน `POSTGRES_PASSWORD` เป็นรหัสสำหรับฐานข้อมูลบนเครื่องก่อนเริ่ม Docker ครั้งแรก ค่าเชื่อมต่อเริ่มต้นคือ:

| ตัวแปร | ค่าเริ่มต้น |
|---|---|
| `POSTGRES_DB` | `superstore_db` |
| `POSTGRES_USER` | `superstore` |
| `POSTGRES_PORT` และ `DB_PORT` | `5433` ทั้งคู่ |
| `DB_HOST` | `localhost` |
| `CSV_PATH` | `data/raw/superstore.csv` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `credentials.json` |
| `GOOGLE_WORKSHEET_NAME` | `dashboard_data` |

Python ติดต่อ `localhost:5433`; PostgreSQL ภายใน container ใช้ port `5432` ถ้า port 5433 ถูกใช้อยู่ ให้เปลี่ยน **ทั้ง** `POSTGRES_PORT` และ `DB_PORT` เป็นค่าเดียวกัน การแก้รหัสผ่านใน `.env` หลังฐานข้อมูลถูกสร้างแล้วจะไม่เปลี่ยนรหัสของผู้ใช้ในฐานข้อมูลเดิมโดยอัตโนมัติ

### 4.4 เปิด PostgreSQL และรอพร้อม

```powershell
docker compose up -d
docker compose ps
```

รอให้ service `db` แสดง **healthy** แล้วจึงรัน Pipeline หากยังไม่พร้อม ตรวจสถานะและ log:

```powershell
docker compose ps
docker compose logs --tail 50 db
```

### 4.5 รันทดสอบเฉพาะฐานข้อมูลก่อน

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --skip-publish
```

คำสั่งนี้ทำ ingest และ transform โดยไม่ต้องมี Google credentials เมื่อสำเร็จจะได้ `raw_data.superstore` และตารางใน `production` พร้อมไฟล์ใน `outputs/`

ตรวจยอดรวมในฐานข้อมูลด้วยค่าผู้ใช้/ชื่อฐานข้อมูลเริ่มต้น:

```powershell
docker compose exec -T db psql -U superstore -d superstore_db -c "SELECT COUNT(*) AS rows, COUNT(DISTINCT order_id) AS orders, SUM(sales) AS sales, SUM(profit) AS profit FROM production.sales_detail;"
```

ถ้าเปลี่ยน `POSTGRES_USER` หรือ `POSTGRES_DB` ให้แก้ค่าหลัง `-U` และ `-d` ตามนั้น เปรียบเทียบกับค่าอ้างอิงในหัวข้อ 2

## 5. ตั้ง Google API Credentials

1. เข้า [Google Cloud Console](https://console.cloud.google.com/) เลือกหรือสร้างโปรเจกต์
2. เปิดใช้งาน **Google Sheets API** และ **Google Drive API**
3. ไปที่ **IAM & Admin > Service Accounts** สร้างบัญชี เช่น `superstore-publisher` การเขียน Spreadsheet ที่แชร์ให้บัญชีนี้ไม่ต้องให้สิทธิ์ Project Editor หรือ Owner
4. เปิดบัญชีนั้น เลือก **Keys > Add key > Create new key > JSON** แล้วดาวน์โหลดไฟล์
5. เก็บไฟล์เป็น `credentials.json` ในโฟลเดอร์โปรเจกต์บนเครื่องตนเอง
6. สร้าง Google Spreadsheet เช่น `Superstore Analytics` ด้วยบัญชี Google ของตนเอง
7. เปิด JSON ในเครื่อง คัดลอกเฉพาะค่า `client_email` แล้วแชร์ Spreadsheet ให้ email นี้เป็น **Editor**
8. คัดลอก Spreadsheet ID จาก URL ส่วนระหว่าง `/d/` และ `/edit` ลงใน `.env` ที่ `GOOGLE_SHEET_ID=` ส่วน `gid` เป็นรหัสแท็บและไม่ใช่ค่าที่ต้องใส่ตรงนี้

เก็บไฟล์ key ไว้ในเครื่อง ไม่ส่งในแชต รายงาน หรือ GitHub `.gitignore` ของโปรเจกต์กัน `credentials.json` และ `.env` ไว้แล้ว

เมื่อตั้งค่าครบ รันทุกขั้นตอน:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py
```

เมื่อใช้ interpreter ของ environment ที่ติดตั้ง dependencies แล้ว คำสั่งหลักตามโจทย์คือ:

```bash
python run_pipeline.py
```

สคริปต์ตรวจไฟล์ credentials และ Spreadsheet ID ก่อนเริ่มรันแบบครบทุกขั้นตอน จากนั้นอ่าน `production.sales_detail` ส่งไปแท็บ `dashboard_data` เป็นชุดละ 1,000 แถว พร้อมรูปแบบวันที่จริงและค่าตัวเลข หากไม่มีแท็บนี้สคริปต์จะสร้างใน Spreadsheet ที่ระบุ ถ้ามีแล้วจะอัปเดตแท็บเดิมและปรับขนาดให้ไม่มีแถวเก่าค้าง

## 6. ตาราง production และความหมายของตัวเลข

| ตาราง | หน้าที่ |
|---|---|
| `sales_detail` | รายการสินค้าที่ทำความสะอาดแล้ว พร้อมวันที่ เดือน ช่วงส่วนลด และจำนวนวันก่อนส่งสินค้า |
| `monthly_summary` | ยอดขายและกำไรรายเดือน |
| `subcategory_summary` | ผลประกอบการตามหมวดหมู่ย่อย |
| `region_summary` | ผลประกอบการตามภูมิภาค |
| `segment_summary` | ผลประกอบการตามกลุ่มลูกค้า |
| `discount_summary` | ผลประกอบการตามช่วงส่วนลด |

เผยแพร่ตาราง detail ไป Sheets เพียงตารางเดียวเพื่อให้ Dashboard กรองได้ครบ ตารางสรุปใช้แสดงการทำ Aggregation และตรวจยอดรวม คำสั่งซื้อที่ไม่ซ้ำในหลายหมวดสินค้าอาจเป็น Order เดียวกัน จึงไม่บวกยอดนับ Order ของแต่ละหมวดเข้าด้วยกัน

อัตรากำไรรวมใช้ `SUM(profit) / SUM(sales)` ไม่เฉลี่ยเปอร์เซ็นต์รายแถว `shipping_days` คือวันจากสั่งซื้อถึงส่งสินค้า ไม่ใช่ระยะเวลาจนลูกค้าได้รับสินค้า

## 7. สร้าง Dashboard และเตรียมส่ง

ทำตาม [คู่มือ Dashboard](docs/dashboard_guide.md) เพื่อเชื่อม Google Sheets และสร้างกราฟครบ 5 คำถาม ใช้วันที่ของข้อมูลจริง 2014–2017 เป็นช่วงเริ่มต้น รายงานที่เสร็จต้องมีลิงก์แชร์ **Anyone with the link can view**

สิ่งที่ต้องจัดเตรียมเพิ่มเติมสำหรับส่งงาน: รายงานโปรเจกต์, GitHub Repository, ลิงก์ Data Studio และหลักฐานการรันจากเครื่องตนเอง ภาพหน้าจอหลักฐานควรมี log Pipeline, ตาราง raw/production, Google Sheets และ Dashboard โดยไม่แสดง key หรือรหัสผ่าน

### นำ Source Code ขึ้น GitHub

Repository ออนไลน์ยังไม่ได้สร้างให้ในขั้นตอนเตรียมไฟล์นี้ หลังติดตั้ง Git และสร้าง repository ปลายทางแล้ว สามารถเริ่มเตรียม commit ในโฟลเดอร์โปรเจกต์ได้:

```powershell
git init
git add .
git diff --cached --name-only
```

ตรวจรายการก่อน commit ต้องไม่มี `.env`, `credentials.json`, service-account key, `.venv/` และข้อมูลดิบใน `data/raw/` ส่วน `.env.example` ต้องมีเพื่อให้ผู้อื่นตั้งค่ารันได้ จากนั้นใช้ remote URL ของ repository ที่สร้างจริงตามขั้นตอนใน GitHub

## 8. หยุดงานและแก้ปัญหา

หยุด PostgreSQL โดยเก็บข้อมูลไว้:

```powershell
docker compose stop
```

เปิดใช้อีกครั้งด้วย `docker compose up -d`

| อาการ | สิ่งที่ตรวจ |
|---|---|
| Docker ติดต่อไม่ได้ | เปิด Docker Desktop และให้ `docker info` ผ่านก่อน |
| Connection refused | รอ `db` healthy และตรวจ `DB_PORT` ตรงกับ `POSTGRES_PORT` |
| Password authentication failed | รหัสใน `.env` ต้องตรงกับผู้ใช้ฐานข้อมูลที่ถูกสร้างไว้แล้ว |
| หา CSV ไม่พบ | ตรวจ `CSV_PATH` และตำแหน่ง `data/raw/superstore.csv` |
| หา credentials ไม่พบ | วาง key ตาม `GOOGLE_APPLICATION_CREDENTIALS` หรือใช้ `--skip-publish` ระหว่างเตรียมฐานข้อมูล |
| `SpreadsheetNotFound` / ไม่มีสิทธิ์ | ตรวจ Spreadsheet ID, เปิด API และแชร์ให้ `client_email` เป็น Editor |
| Dashboard ว่าง | เลือกแท็บถูกต้อง ตรวจวันที่เป็น Date และช่วงวันที่ครอบคลุมปี 2014–2017 |
| การส่งข้อมูลล้มเหลวกลางทาง | แก้สาเหตุแล้วรันใหม่ และตรวจจำนวนแถว/ยอดรวมหลังรันสำเร็จ |

## 9. เอกสารอ้างอิง

- Dataset: https://www.kaggle.com/datasets/vivek468/superstore-dataset-final
- Python venv: https://docs.python.org/3.12/library/venv.html
- Docker Compose: https://docs.docker.com/compose/gettingstarted/
- Docker Compose stop: https://docs.docker.com/reference/cli/docker/compose/stop/
- gspread authentication: https://docs.gspread.org/en/master/oauth2.html
- Service-account keys: https://docs.cloud.google.com/iam/docs/keys-create-delete
- gspread Worksheet API: https://docs.gspread.org/en/master/api/models/worksheet.html
- Google Sheets date formats: https://developers.google.com/workspace/sheets/api/guides/formats
- Google Sheets API limits: https://developers.google.com/workspace/sheets/api/limits

