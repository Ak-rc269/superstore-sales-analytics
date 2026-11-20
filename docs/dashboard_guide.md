# คู่มือสร้าง Superstore Dashboard ใน Data Studio

คู่มือนี้ใช้หลังรัน `python run_pipeline.py` จนเผยแพร่ข้อมูลสำเร็จ โดยข้อมูลใน Google Sheets ต้องอยู่ที่ Worksheet `dashboard_data` เอกสารนี้เป็นแผนและขั้นตอนสร้างรายงาน ไม่ใช่ลิงก์ Dashboard ที่สร้างเสร็จแล้ว

## 1. ตรวจ Google Sheets ก่อนเชื่อม

- แถวแรกเป็นชื่อคอลัมน์ ไม่มีเซลล์รวมและไม่มีแถว Total ต่อท้าย
- เมื่อไม่มี filter จำนวนข้อมูลควรเป็น **9,994 แถว** บวก header อีกหนึ่งแถว
- `order_date`, `ship_date`, `order_month` เป็นวันที่จริง สคริปต์ใช้เลข serial และกำหนด DATE format ให้แล้ว
- `sales`, `profit`, `quantity`, `discount` เป็นตัวเลข ส่วนรหัสลูกค้า คำสั่งซื้อ สินค้า และไปรษณีย์เป็นข้อความ
- คอลัมน์ `sub_category` ใช้ชื่อนี้ตามโค้ด ไม่ใช่ `subcategory`

ตารางนี้มีรายการสินค้าใน Order เดียวกันได้หลายแถว จึงใช้ `COUNT_DISTINCT(order_id)` เพื่อหาจำนวนคำสั่งซื้อ

## 2. สร้าง Data Source

1. เปิด [Data Studio](https://datastudio.google.com/) ด้วยบัญชีที่เข้าถึง Spreadsheet
2. เลือก **Create > Data Source > Google Sheets**
3. เลือก Spreadsheet ของโปรเจกต์และ Worksheet **dashboard_data**
4. เปิด **Use first row as headers** แล้วกด **CONNECT**
5. ตรวจชนิดข้อมูลตามตารางด้านล่าง จากนั้นสร้าง Report

| ฟิลด์ | Type | การสรุปค่า / หมายเหตุ |
|---|---|---|
| `order_date`, `ship_date`, `order_month` | Date | ใช้เป็นมิติวันที่ |
| `sales`, `profit`, `quantity` | Number | Sum |
| `discount` | Percent | ส่วนลด 0.2 หมายถึง 20%; ถ้าใช้ค่าเฉลี่ยให้ระบุว่าเป็นค่าเฉลี่ยรายแถว |
| `region`, `category`, `sub_category`, `segment`, `discount_band` | Text | ใช้เป็น dimension และตัวกรอง |
| `order_id`, `customer_id`, `product_id`, `postal_code` | Text | ห้ามใช้ Sum กับรหัส |
| `discount_band_sort` | Number | ใช้จัดลำดับช่วงส่วนลด |

หากวันที่ถูกอ่านเป็น Number ให้ตรวจ DATE format ใน Google Sheets แล้วรีเฟรชหรือเชื่อม Data Source ใหม่ก่อนตรวจชนิดฟิลด์อีกครั้ง เลือก `order_date` เป็น Date range dimension ของกราฟ

Google ใช้ชื่อ Data Studio ในเอกสารที่อ้างอิงด้านล่าง บางหน้าความช่วยเหลือหรือบัญชีอาจยังแสดงชื่อ Looker Studio

## 3. สร้าง Metric ที่ใช้ร่วมกัน

เพิ่ม Calculated field ที่ Data Source หรือระดับกราฟตามหน้าจอที่ใช้งาน:

| ชื่อที่แสดง | สูตร | รูปแบบ |
|---|---|---|
| Total Sales | `SUM(sales)` | Number, ทศนิยม 2 ตำแหน่ง |
| Total Profit | `SUM(profit)` | Number, ทศนิยม 2 ตำแหน่ง |
| Profit Margin | `SUM(profit) / SUM(sales)` | Percent, ทศนิยม 2 ตำแหน่ง |
| Orders | `COUNT_DISTINCT(order_id)` | Number, ไม่มีทศนิยม |
| Customers | `COUNT_DISTINCT(customer_id)` | Number, ไม่มีทศนิยม |

Profit Margin ต้องคำนวณจากผลรวมเพื่อให้น้ำหนักตามยอดขาย ไม่ใช้ `AVG(profit_margin)` สูตรที่กำหนด aggregation ไว้แล้วใช้ค่า aggregation เป็น Auto

### ค่าอ้างอิงเมื่อยังไม่กรองข้อมูล

| Metric | ค่าที่ควรได้ |
|---|---:|
| Total Sales | 2,297,200.86 |
| Total Profit | 286,397.02 |
| Profit Margin | 12.47% |
| Orders | 5,009 |
| Customers | 793 |

CSV ไม่ได้ระบุคอลัมน์สกุลเงิน ให้แสดงชื่อยอดขาย/กำไรและหมายเหตุว่าใช้หน่วยตามข้อมูลต้นทาง ไม่เปลี่ยนหน่วยเป็นบาทโดยอัตโนมัติ ค่าอ้างอิงนี้มาจาก CSV ที่แนบและใช้ตรวจ Dashboard ไม่ใช่ผลการเชื่อม Google Sheets ที่ยืนยันแล้ว

## 4. กราฟ 5 ข้อตามคำถามธุรกิจ

### กราฟ 1 — ยอดขายและกำไรเปลี่ยนแปลงรายเดือนอย่างไร

| การตั้งค่า | ค่า |
|---|---|
| Chart | Time series |
| Dimension | `order_month` โดยใช้ระดับ Year Month |
| Metrics | Total Sales และ Total Profit |
| Sort | วันที่จากเก่าไปใหม่ |
| Date range dimension | `order_date` |

ใช้เดือนพร้อมปีเพื่อไม่รวมมกราคมของหลายปีเข้าด้วยกัน ถ้าใช้แกนที่สองสำหรับกำไร ต้องระบุชื่อและหน่วยแกนให้ชัด อ่านทั้งการเปลี่ยนแปลงยอดขายและกำไร ไม่สรุปจากยอดขายเพียงค่าเดียว

### กราฟ 2 — หมวดหมู่ย่อยใดขายสูงแต่กำไรต่ำหรือขาดทุน

| การตั้งค่า | ค่า |
|---|---|
| Chart | Scatter chart |
| Dimension | `sub_category` |
| X metric | Total Sales |
| Y metric | Total Profit |
| เส้นอ้างอิง | กำไร = 0 ถ้าตัวเลือกกราฟรองรับ |

จุดใต้เส้นกำไรศูนย์คือหมวดที่ขาดทุนรวมในข้อมูลที่เลือก อาจเพิ่มตารางเล็กที่แสดง `sub_category`, Total Sales, Total Profit และ Profit Margin เพื่ออ่านค่าของจุดได้ง่าย

### กราฟ 3 — ภูมิภาคใดสร้างกำไรมากที่สุด

| การตั้งค่า | ค่า |
|---|---|
| Chart | Horizontal bar |
| Dimension | `region` |
| Metric | Total Profit |
| Sort | Total Profit จากมากไปน้อย |

ใช้สีแยกค่าบวกและลบเมื่อเหมาะสม หากเปรียบเทียบประสิทธิภาพร่วมด้วย ให้แสดง Profit Margin ในตารางประกอบ ไม่ตีความกำไรรวมสูงว่าอัตรากำไรต้องสูงเสมอ

### กราฟ 4 — กลุ่มลูกค้าใดสร้างยอดขายและกำไรมากที่สุด

| การตั้งค่า | ค่า |
|---|---|
| Chart | Grouped bar หรือ Combo chart |
| Dimension | `segment` |
| Metrics | Total Sales และ Total Profit |
| Sort | Total Sales จากมากไปน้อย |

ถ้าต้องการแสดงจำนวนลูกค้าร่วม ให้ใช้ Customers ที่เป็น `COUNT_DISTINCT(customer_id)` การมีหลายรายการสินค้าต่อคนไม่ทำให้จำนวนลูกค้าเพิ่มซ้ำ

### กราฟ 5 — ระดับส่วนลดสัมพันธ์กับอัตรากำไรอย่างไร

| การตั้งค่า | ค่า |
|---|---|
| Chart | Bar chart |
| Dimension | `discount_band` |
| Metric | Profit Margin |
| Sort | `discount_band_sort` จากน้อยไปมาก ใช้ Min สำหรับลำดับของแต่ละกลุ่ม |

ช่วงส่วนลดตามโค้ดคือ `0%`, `(0%, 20%]`, `(20%, 40%]`, `>40%` โดย 20% อยู่กลุ่มที่สอง และ 40% อยู่กลุ่มที่สาม ทุกกลุ่มคำนวณอัตรากำไรจาก `SUM(profit)/SUM(sales)`

ใช้คำว่า “สัมพันธ์กับ” เมื่ออธิบายผล ไม่สรุปว่าส่วนลดเป็นสาเหตุเพียงอย่างเดียวของกำไรหรือขาดทุน เพราะหมวดสินค้า พื้นที่ และกลุ่มลูกค้าที่อยู่ในแต่ละช่วงอาจต่างกัน

## 5. ตัวกรองและโครงหน้ารายงาน

เสนอให้ใช้รายงาน 2 หน้าเพื่ออ่านได้ชัด: หน้า Overview แสดง KPI, กราฟรายเดือนและภูมิภาค; หน้า Product & Customer แสดงกราฟหมวดหมู่ย่อย กลุ่มลูกค้า และส่วนลด การแบ่ง 2 หน้าเป็นข้อเสนอการจัดวาง ไม่ใช่ข้อบังคับของโจทย์

เพิ่ม Date range control และ Drop-down สำหรับ `region`, `category`, `segment` โดยทุกกราฟใช้ Data Source `dashboard_data` เดียวกัน ตั้งช่วงวันที่เริ่มต้น **3 มกราคม 2014 ถึง 30 ธันวาคม 2017** หรือช่วงที่ครอบคลุมข้อมูลทั้งหมด อย่าใช้ Last 28 days กับข้อมูลย้อนหลังนี้

หลังเพิ่ม filter ให้เลือกหนึ่งภูมิภาคและตรวจว่ากราฟทุกอันเปลี่ยนสอดคล้องกัน จากนั้นคืนค่าทั้งหมดก่อนบันทึกหน้าที่จะใช้ในการนำเสนอ

## 6. ตรวจผลและแชร์เพื่อส่งงาน

1. เทียบ KPI กับค่าอ้างอิงในหัวข้อ 3 ขณะที่ไม่มีตัวกรอง
2. ตรวจกราฟรายเดือนเรียงวันที่ถูกต้องและมีปีประกอบ
3. ตรวจกราฟส่วนลดใช้ Profit Margin แบบผลรวม ไม่เฉลี่ยเปอร์เซ็นต์รายแถว
4. รัน Pipeline ซ้ำหนึ่งครั้งแล้วรีเฟรชข้อมูล ตรวจว่าจำนวนข้อมูลและยอดรวมไม่เพิ่มเป็นสองเท่า
5. เปิด Report > **Share > Link settings > Anyone with the link can view** และคัดลอกลิงก์
6. ทดสอบลิงก์ในหน้าต่างที่ไม่ได้ลงชื่อเข้าใช้ หากไม่มีสิทธิ์ ให้ตรวจการแชร์รายงานและ Data credentials

การใช้ **Owner's credentials** ทำให้ผู้ชมรายงานเข้าถึงผลวิเคราะห์ได้โดยไม่ต้องแชร์ Spreadsheet ให้ผู้ชมทุกคน ไฟล์ `credentials.json` ใช้เฉพาะ Python บนเครื่องและไม่ต้องแนบในรายงาน

สำหรับรายงานโปรเจกต์ ให้บันทึกคำถามแต่ละข้อ กราฟที่ตอบคำถาม ค่าตัวเลขที่อ่านได้จริง และข้อเสนอที่สอดคล้องกับข้อมูล อย่าใส่ข้อความว่าทดสอบการเผยแพร่สำเร็จจนกว่าจะรันจริงและตรวจผลในบัญชีแล้ว

## 7. เอกสารอ้างอิง

- Google Sheets connector: https://docs.cloud.google.com/data-studio/connect-to-google-sheets
- การจัดตารางและวันที่: https://docs.cloud.google.com/data-studio/tutorial-create-a-google-sheets-data-source
- Calculated fields: https://docs.cloud.google.com/data-studio/about-calculated-fields
- Count distinct: https://docs.cloud.google.com/data-studio/countdistinct
- การแชร์ Report: https://docs.cloud.google.com/data-studio/invite-others-to-your-reports
- วันที่ใน Google Sheets API: https://developers.google.com/workspace/sheets/api/guides/formats

