from pathlib import Path
from openpyxl import Workbook
import csv
root=Path(__file__).resolve().parents[1]
folder=root/'test-data';folder.mkdir(exist_ok=True)
headers=['备注1','备注2','备注3','备注4','备注5','物料编码','备注7','备注8','数量','单价']
for n in (10,100,300):
    records=[['','','','','',f'MAT-{i:03d}','','','2','3.50'] for i in range(1,n+1)]
    book=Workbook();ws=book.active;ws.title='采购明细';ws.append(headers)
    for row in records:ws.append(row)
    book.save(folder/f'test_{n}.xlsx')
    for ext,delimiter in [('csv',','),('tsv','\t')]:
        with (folder/f'test_{n}.{ext}').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f,delimiter=delimiter);w.writerow(headers);w.writerows(records)
print(folder)
