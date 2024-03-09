from idlelib import query

from flask import Flask, render_template, redirect, request, session
import sqlite3
from sqlite3 import Error
from flask_bcrypt import Bcrypt

# DATABASE = "C:/Users/GGPC/PycharmProjects/Smile/smile.db" # Desktop
DATABASE = "C:/Users/ethan/PycharmProjects/SmileCafe/smile.db"  # Laptop

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = "qwertyuiop"


def create_connection(db_file):
    try:
        connection = sqlite3.connect(db_file)
        return connection
    except Error as e:
        print(e)
    return None


def is_logged_in():
    if session.get('email') is None:
        return False
    else:
        return True


def is_admin():
    if session.get('is_admin') is not 1:
        return False
    else:
        return True


def is_ordering():
    if session.get('order') is None:
        return False
    else:
        return True


def get_list(query, params):
    con = create_connection(DATABASE)
    cur = con.cursor()
    if params == "":
        cur.execute(query)
    else:
        cur.execute(query, params)
    query_list = cur.fetchall()
    con.close()
    return query_list


def put_data(query, params):
    con = create_connection(DATABASE)
    cur = con.cursor()
    cur.execute(query, params)
    con.commit()
    con.close()


def summarise_order():
    order = session.get('order')
    order.sort()
    order_summary = []
    last_order = -1
    for item in order:
        if item != last_order:
            order_summary.append([item, 1])
            last_order = item
        else:
            order_summary[-1][1] += 1
    return order_summary


@app.route('/')
def render_homepage():
    return render_template('home.html', logged_in=is_logged_in(), is_admin=is_admin())


@app.route('/menu/<cat_id>')
def render_menu_page(cat_id):
    category_list = get_list("SELECT * FROM category", "")
    product_list = get_list("SELECT id, name, description, volume, image, price FROM products WHERE cat_id=?", (cat_id, ))

    order_start = request.args.get('order')
    if order_start == "start" and not is_ordering():
        session['order'] = []

    return render_template('menu.html', categories=category_list, products=product_list, logged_in=is_logged_in(), is_admin=is_admin(), ordering=is_ordering())


@app.route("/add_to_cart/<product_id>")
def add_to_cart(product_id):
    try:
        product_id = int(product_id)
    except ValueError:
        return redirect("/menu/1?error=Invalid+product+id")
    order = session['order']
    order.append(product_id)
    session['order'] = order
    return redirect(request.referrer)


@app.route("/cart", methods=["GET", "POST"])
def render_cart():
    if request.method == "POST":
        name = request.form['name']
        put_data("INSERT INTO orders VALUES (null, ?, TIME('now'), ?)", (name, 1))
        order_number = get_list("SELECT max(id) FROM orders WHERE name = ?", (name, ))
        order_number = order_number[0][0]
        orders = summarise_order()
        for order in orders:
            put_data("INSERT INTO order_contents VALUES (NULL, ?, ?, ?)", (order_number, order[0], order[1]))
        session.pop('order')
        return redirect('/?message=Order+has+been+placed+under+the+name+' + name)
    else:
        orders = summarise_order()
        total = 0
        for item in orders:
            item_detail = get_list("SELECT name, price FROM products WHERE id = ?", (item[0], ))
            if item_detail:
                item.append(item_detail[0][0])
                item.append(item_detail[0][1])
                item.append(item_detail[0][1] * item[1])
                total += item_detail[0][1] * item[1]
        return render_template("cart.html", logged_in=is_logged_in(), is_admin=is_admin(), ordering=is_ordering(), products=orders, total=total)


@app.route('/cancel_order')
def cancel_order():
    if session.get('order') is not None:
        session.pop('order')
    return redirect('/')


@app.route('/process_order/<processed>')
def render_process_order(processed):
    label = "processed"
    if processed == "1":
        label = "un" + label
    processed = int(processed)
    all_orders = get_list("SELECT orders.id, orders.name, timestamp, products.name, quantity, price from orders INNER JOIN order_contents ON orders.id = order_contents.order_id INNER JOIN products ON order_contents.product_id = products.id WHERE processed = ?", (processed, ))
    print(all_orders)
    return render_template("orders.html", orders=all_orders, label=label, logged_in=is_logged_in(), is_admin=is_admin())


@app.route('/process/<order_id>')
def process_order(order_id):
    put_data("UPDATE orders SET processed = 0 WHERE id = ?", (order_id, ))
    return redirect(request.referrer)


@app.route('/contact')
def render_contact_page():
    return render_template('contact.html')


@app.route('/login', methods=['POST', 'GET'])
def render_login():
    if is_logged_in():
        return redirect('/menu/1')
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        query = """SELECT id, fname, password, is_admin FROM user WHERE email= ?"""
        con = create_connection(DATABASE)
        cur = con.cursor()
        cur.execute(query, (email,))
        user_data = cur.fetchone()
        con.close()
        try:
            user_id = user_data[0]
            first_name = user_data[1]
            db_password = user_data[2]
            is_admin = user_data[3]
        except IndexError:
            return redirect('/login?error=Invalid+username+or+password')

        if not bcrypt.check_password_hash(db_password, password):
            return redirect(request.referrer + "?error=Email+invalid+or+password+incorrect")

        session['email'] = email
        session['user_id'] = user_id
        session['firstname'] = first_name
        session['is_admin'] = is_admin
        return redirect('/')

    return render_template('login.html')


@app.route('/logout')
def logout():
    [session.pop(key) for key in list(session.keys())]
    return redirect('/?message=See+you+next+time!')


@app.route('/signup', methods=['POST', 'GET'])
def render_signup():
    if is_logged_in():
        return redirect('/menu/1')
    if request.method == 'POST':
        fname = request.form.get('fname').title().strip()
        lname = request.form.get('lname').title().strip()
        email = request.form.get('email').lower().strip()
        password = request.form.get('password')
        password2 = request.form.get('password2')
        admin = 0
        if request.form.get('is_admin') == 'on':
            admin = 1

        if password != password2:
            return redirect('\signup?error=Passwords+do+not+match')

        if len(password) < 8:
            return redirect('/signup?error=Passwords+must+be+at+least+8+characters')

        hashed_password = bcrypt.generate_password_hash(password)

        try:
            put_data('INSERT INTO user (fname, lname, email, password, is_admin) VALUES (?, ?, ?, ?, ?)', (fname, lname, email, hashed_password, admin))
        except sqlite3.IntegrityError:
            return redirect('/signup?error=Email+is+already+used')

        return redirect('/login')

    return render_template('signup.html', logged_in=is_logged_in(), is_admin=is_admin())


@app.route('/admin')
def render_admin():
    if not is_logged_in():
        return redirect('/?message=Need+to+be+logged+in.')
    category_list = get_list("SELECT * FROM category", "")

    return render_template("admin.html", logged_in=is_logged_in(), is_admin=is_admin(), categories=category_list)


@app.route('/add_category', methods=['POST'])
def add_category():
    if not is_logged_in():
        return redirect('/?message=Need+to+be+logged+in.')
    if request.method == "POST":
        cat_name = request.form.get('name').lower().strip()
        put_data('INSERT INTO category (name) VALUES (?)', (cat_name,))
        return redirect('/admin')


@app.route('/delete_category', methods=['POST'])
def render_delete_category():
    if not is_logged_in():
        return redirect('/?message=Need+to+be+logged+in.')
    if request.method == "POST":
        category = request.form.get('cat_id')
        category = category.split(", ")
        cat_id = category[0]
        cat_name = category[1]
        return render_template("delete_confirm.html", id=cat_id, name=cat_name, type="category", logged_in=is_logged_in(), is_admin=is_admin())
    return redirect('/admin')


@app.route('/delete_category_confirm/<category_id>')
def delete_category_confirm(category_id):
    if not is_logged_in():
        return redirect('/?message=Need+tobe+logged+in.')
    con = create_connection(DATABASE)
    query = 'DELETE FROM category WHERE id = ?'
    cur = con.cursor()
    cur.execute(query, (category_id,))
    con.commit()
    con.close()
    return redirect('/admin')


if __name__ == '__main__':
    app.run()
