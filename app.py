from datetime import date
from pathlib import Path
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'accounting.db'
app = Flask(__name__)
app.secret_key = 'accounting-web-local-key'

DEFAULT_CATS = [
    ('薪資收入','收入'), ('股利收入','收入'), ('副業收入','收入'),
    ('餐飲食品','支出'), ('交通通訊','支出'), ('居家生活','支出'),
    ('娛樂休閒','支出'), ('醫療保健','支出'), ('其他支出','支出')]
DEFAULT_STOCK_CATS = [('個股買賣',), ('定期定額',), ('現金股利',), ('既有持股結算',)]
DEFAULT_FREQS = [('非股利',0.0), ('每月',12.0), ('每兩月',6.0), ('每季',4.0), ('半年',2.0), ('每年',1.0), ('每兩年',0.5)]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, type TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS dividend_frequencies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, times_per_year REAL NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, type TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL, note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, stock_code TEXT NOT NULL DEFAULT '',
        stock_name TEXT NOT NULL DEFAULT '', trade_type TEXT NOT NULL, initial_capital REAL NOT NULL DEFAULT 0,
        expense_amount REAL NOT NULL DEFAULT 0, income_amount REAL NOT NULL DEFAULT 0, profit_loss REAL NOT NULL DEFAULT 0,
        shares INTEGER NOT NULL DEFAULT 0, has_dividend INTEGER NOT NULL DEFAULT 0, dividend_per_share REAL NOT NULL DEFAULT 0,
        freq_label TEXT NOT NULL DEFAULT '非股利', freq_times REAL NOT NULL DEFAULT 0,
        monthly_avg_dividend REAL NOT NULL DEFAULT 0, note TEXT)''')
    if c.execute('SELECT COUNT(*) n FROM categories').fetchone()['n'] == 0: c.executemany('INSERT INTO categories(name,type) VALUES(?,?)', DEFAULT_CATS)
    if c.execute('SELECT COUNT(*) n FROM stock_categories').fetchone()['n'] == 0: c.executemany('INSERT INTO stock_categories(name) VALUES(?)', DEFAULT_STOCK_CATS)
    if c.execute('SELECT COUNT(*) n FROM dividend_frequencies').fetchone()['n'] == 0: c.executemany('INSERT INTO dividend_frequencies(name,times_per_year) VALUES(?,?)', DEFAULT_FREQS)
    conn.commit(); conn.close()


def years(table):
    conn=db(); rows=conn.execute(f"SELECT DISTINCT substr(date,1,4) y FROM {table} WHERE date LIKE '____-__-__' ORDER BY y DESC").fetchall(); conn.close()
    vals=[r['y'] for r in rows if r['y']]
    now=str(date.today().year)
    if now not in vals: vals.insert(0, now)
    return vals


def filters(prefix):
    y=request.args.get(f'{prefix}_year','全部'); m=request.args.get(f'{prefix}_month','全部')
    return y,m


def where_date(y,m):
    clauses=[]; params=[]
    if y and y!='全部': clauses.append('date LIKE ?'); params.append(f'{y}-%')
    if m and m!='全部': clauses.append('substr(date,6,2)=?'); params.append(m)
    return (' AND '+ ' AND '.join(clauses)) if clauses else '', params


def dashboard_data(dy='全部',dm='全部',sy='全部',sm='全部'):
    conn=db()
    inc=conn.execute("SELECT COALESCE(SUM(amount),0) v FROM transactions WHERE type='收入'").fetchone()['v']
    exp=conn.execute("SELECT COALESCE(SUM(amount),0) v FROM transactions WHERE type='支出'").fetchone()['v']
    wc,pc=where_date(dy,dm)
    r=conn.execute(f"SELECT COALESCE(SUM(CASE WHEN type='收入' THEN amount ELSE 0 END),0) inc, COALESCE(SUM(CASE WHEN type='支出' THEN amount ELSE 0 END),0) exp FROM transactions WHERE 1=1{wc}",pc).fetchone()
    ws,ps=where_date(sy,sm)
    s=conn.execute(f"SELECT COALESCE(SUM(initial_capital),0) initial, COALESCE(SUM(expense_amount),0) expense, COALESCE(SUM(income_amount),0) income, COALESCE(SUM(profit_loss),0) pl, COALESCE(SUM(monthly_avg_dividend),0) dividend FROM stock_trades WHERE 1=1{ws}",ps).fetchone()
    all_s=conn.execute("SELECT COALESCE(SUM(initial_capital),0) initial, COALESCE(SUM(expense_amount),0) expense, COALESCE(SUM(income_amount),0) income, COALESCE(SUM(profit_loss),0) pl, COALESCE(SUM(monthly_avg_dividend),0) dividend FROM stock_trades").fetchone()
    conn.close()
    return {'cash_income':inc,'cash_expense':exp,'cash_balance':inc-exp,'filtered_income':r['inc'],'filtered_expense':r['exp'],
            'stock_initial':all_s['initial'],'stock_expense':all_s['expense'],'stock_income':all_s['income'],'stock_pl':all_s['pl'],'monthly_dividend':all_s['dividend'],
            'stock_filtered':dict(s), 'net_assets':inc-exp+all_s['initial']+all_s['pl']}


@app.route('/')
def index():
    dy,dm=filters('daily'); sy,sm=filters('stock')
    conn=db()
    cats=conn.execute('SELECT * FROM categories ORDER BY type DESC,id').fetchall()
    stock_cats=conn.execute('SELECT * FROM stock_categories ORDER BY id').fetchall()
    freqs=conn.execute('SELECT * FROM dividend_frequencies ORDER BY id').fetchall()
    wc,pc=where_date(dy,dm)
    daily=conn.execute(f'SELECT id,date,type,category,amount,note FROM transactions WHERE 1=1{wc} ORDER BY date DESC,id DESC',pc).fetchall()
    ws,ps=where_date(sy,sm)
    stocks=conn.execute(f'''SELECT id,date,stock_code,stock_name,trade_type,initial_capital,expense_amount,income_amount,profit_loss,shares,freq_label,monthly_avg_dividend,note FROM stock_trades WHERE 1=1{ws} ORDER BY date DESC,id DESC''',ps).fetchall()
    conn.close()
    return render_template('index.html', daily=daily, stocks=stocks, cats=cats, stock_cats=stock_cats, freqs=freqs,
                           daily_years=years('transactions'), stock_years=years('stock_trades'), dy=dy,dm=dm,sy=sy,sm=sm,
                           data=dashboard_data(dy,dm,sy,sm), today=date.today().isoformat())


@app.post('/daily/add')
def daily_add():
    try:
        amount=float(request.form['amount'])
        if amount<=0: raise ValueError
        conn=db(); conn.execute('INSERT INTO transactions(date,type,category,amount,note) VALUES(?,?,?,?,?)',
            (request.form['date'],request.form['type'],request.form['category'],amount,request.form.get('note','').strip())); conn.commit(); conn.close(); flash('收支紀錄已新增。','success')
    except Exception: flash('請確認日期、類別與金額格式。','error')
    return redirect(url_for('index', daily_year=request.form.get('daily_year','全部'), daily_month=request.form.get('daily_month','全部'))+'#daily')

@app.post('/daily/delete/<int:item_id>')
def daily_delete(item_id):
    conn=db(); conn.execute('DELETE FROM transactions WHERE id=?',(item_id,)); conn.commit(); conn.close(); flash('收支紀錄已刪除。','success'); return redirect(url_for('index')+'#daily')

@app.post('/stock/add')
def stock_add():
    try:
        initial=float(request.form.get('initial_capital') or 0); expense=float(request.form.get('expense_amount') or 0); income=float(request.form.get('income_amount') or 0); shares=int(request.form.get('shares') or 0)
        has_div=1 if request.form.get('has_dividend') else 0
        div=float(request.form.get('dividend_per_share') or 0) if has_div else 0
        freq=request.form.get('freq_label','非股利') if has_div else '非股利'
        conn=db(); fr=conn.execute('SELECT times_per_year FROM dividend_frequencies WHERE name=?',(freq,)).fetchone(); times=float(fr['times_per_year']) if fr else 0
        monthly=div*shares*times/12 if has_div else 0
        conn.execute('''INSERT INTO stock_trades(date,stock_code,stock_name,trade_type,initial_capital,expense_amount,income_amount,profit_loss,shares,has_dividend,dividend_per_share,freq_label,freq_times,monthly_avg_dividend,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (request.form['date'],request.form.get('stock_code','').strip(),request.form.get('stock_name','').strip() or request.form.get('stock_code','').strip() or '未填寫',request.form['trade_type'],initial,expense,income,income-expense,shares,has_div,div,freq,times,monthly,request.form.get('note','').strip()))
        conn.commit(); conn.close(); flash('股票紀錄已新增。','success')
    except Exception: flash('請確認股票紀錄中的數字與必要欄位。','error')
    return redirect(url_for('index', stock_year=request.form.get('stock_year','全部'), stock_month=request.form.get('stock_month','全部'))+'#stock')

@app.post('/stock/delete/<int:item_id>')
def stock_delete(item_id):
    conn=db(); conn.execute('DELETE FROM stock_trades WHERE id=?',(item_id,)); conn.commit(); conn.close(); flash('股票紀錄已刪除。','success'); return redirect(url_for('index')+'#stock')

@app.post('/settings/category/add')
def category_add():
    try:
        conn=db(); conn.execute('INSERT INTO categories(name,type) VALUES(?,?)',(request.form['name'].strip(),request.form['type'])); conn.commit(); conn.close(); flash('收支類別已新增。','success')
    except sqlite3.IntegrityError: flash('該收支類別已存在。','error')
    return redirect(url_for('index')+'#settings')

@app.post('/settings/category/delete/<int:item_id>')
def category_delete(item_id):
    conn=db(); conn.execute('DELETE FROM categories WHERE id=?',(item_id,)); conn.commit(); conn.close(); flash('收支類別已刪除。','success'); return redirect(url_for('index')+'#settings')

@app.post('/settings/stock-category/add')
def stock_category_add():
    try:
        conn=db(); conn.execute('INSERT INTO stock_categories(name) VALUES(?)',(request.form['name'].strip(),)); conn.commit(); conn.close(); flash('股票交易類型已新增。','success')
    except sqlite3.IntegrityError: flash('該股票交易類型已存在。','error')
    return redirect(url_for('index')+'#settings')

@app.post('/settings/stock-category/delete/<int:item_id>')
def stock_category_delete(item_id):
    conn=db(); conn.execute('DELETE FROM stock_categories WHERE id=?',(item_id,)); conn.commit(); conn.close(); flash('股票交易類型已刪除。','success'); return redirect(url_for('index')+'#settings')

@app.post('/settings/frequency/add')
def frequency_add():
    try:
        times=float(request.form['times']);
        if times<0: raise ValueError
        conn=db(); conn.execute('INSERT INTO dividend_frequencies(name,times_per_year) VALUES(?,?)',(request.form['name'].strip(),times)); conn.commit(); conn.close(); flash('配息週期已新增。','success')
    except sqlite3.IntegrityError: flash('該配息週期已存在。','error')
    except Exception: flash('每年配息次數請輸入大於等於 0 的數字。','error')
    return redirect(url_for('index')+'#settings')

@app.post('/settings/frequency/delete/<int:item_id>')
def frequency_delete(item_id):
    conn=db(); conn.execute('DELETE FROM dividend_frequencies WHERE id=?',(item_id,)); conn.commit(); conn.close(); flash('配息週期已刪除。','success'); return redirect(url_for('index')+'#settings')

@app.get('/api/stock/<code>')
def stock_lookup(code):
    try:
        r=requests.get('https://api.finmindtrade.com/api/v4/data',params={'dataset':'TaiwanStockInfo','data_id':code},headers={'User-Agent':'Mozilla/5.0'},timeout=6); r.raise_for_status(); rows=r.json().get('data',[])
        return jsonify({'ok':bool(rows),'name':rows[0].get('stock_name','') if rows else ''})
    except Exception as e: return jsonify({'ok':False,'error':str(e)}),502

@app.context_processor
def inject():
    return {'money': lambda x: f'${x:,.2f}'}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    init_db()
