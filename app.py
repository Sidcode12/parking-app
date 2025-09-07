from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app=Flask(__name__)
app.secret_key='sid_proj_mad1'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///parking.db'
db=SQLAlchemy(app)

class User(db.Model):
    __name__='user'
    id=db.Column(db.Integer, primary_key=True)
    username=db.Column(db.String(80), unique=True, nullable=False)
    password=db.Column(db.String(120), nullable=False)
    reservations=db.relationship('Reservation', backref='user')
    histories=db.relationship('History',backref='user')

class History(db.Model):
    __name__='history'
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp=db.Column(db.DateTime, default=None)
    leaving_timestamp=db.Column(db.DateTime, default=None)
    price=db.Column(db.Float,default=None)

class ParkingLot(db.Model):
    __name__='parking_lot'
    id=db.Column(db.Integer, primary_key=True)
    prime_location_name=db.Column(db.String(50), nullable=False)
    price=db.Column(db.Float, nullable=False)
    address=db.Column(db.String(100), nullable=False)
    pin_code=db.Column(db.String(10), nullable=False)
    max_spots=db.Column(db.Integer, nullable=False)
    available=db.Column(db.Integer, nullable=False)
    spots=db.relationship('ParkingSpot', backref='lot', cascade='all')

class ParkingSpot(db.Model):
    __name__='parking_spot'
    id=db.Column(db.Integer, primary_key=True)
    lot_id=db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status=db.Column(db.String(1), default='A') 
    reservation=db.relationship('Reservation', backref='spot', uselist=False, cascade='all')

class Reservation(db.Model):
    __name__='reservation'
    id=db.Column(db.Integer, primary_key=True)
    spot_id=db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parking_timestamp=db.Column(db.DateTime, default=datetime.utcnow)
    leaving_timestamp=db.Column(db.DateTime, nullable=True)
    cost=db.Column(db.Float, nullable=True)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username=request.form['username']
        password=request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
        else:
            db.session.add(User(username=username, password=password))
            db.session.commit()
            flash('Registered successfully')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username=request.form['username']
        password=request.form['password']
        user=User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id']=user.id
            session['username']=user.username
            if user.username == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('username') != 'admin':
        return redirect(url_for('login'))
    lots=ParkingLot.query.all()
    users=User.query.all()
    return render_template('admin_dashboard.html', lots=lots, users=users)

@app.route('/admin/create_lot', methods=['GET','POST'])
def create_lot():
    if request.method == 'POST':
        name=request.form['name']
        price=float(request.form['price'])
        address=request.form['address']
        pin=request.form['pin']
        max_spots=int(request.form['max_spots'])
        available=max_spots
        lot=ParkingLot(prime_location_name=name, price=price, address=address, pin_code=pin, max_spots=max_spots,available=available)
        db.session.add(lot)
        db.session.commit()
        for i in range(max_spots):
            db.session.add(ParkingSpot(lot_id=lot.id))
        db.session.commit()
        flash('Parking lot created')
        return redirect(url_for('admin_dashboard'))
    return render_template('create_lot.html')

@app.route('/admin/delete_lot/<int:lot_id>', methods=['POST'])
def delete_lot(lot_id):
    if session.get('username') != 'admin':
        abort(403)

    lot=ParkingLot.query.get(lot_id)
    if not lot:
        abort(404)
    occupied=any(spot.status == 'O' for spot in lot.spots)

    if occupied:
        flash('Cannot delete lot. One or more spots are still occupied.', 'danger')
    else:
        db.session.delete(lot)
        db.session.commit()
        flash(f'Parking lot "{lot.prime_location_name}" deleted successfully.', 'success')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if session.get('username') != 'admin':
        abort(403)
    
    lot=ParkingLot.query.get(lot_id)
    if not lot:
        abort(404)
    
    if request.method == 'POST':
        new_max_spots=request.form.get('max_spots')
        if not new_max_spots:
            flash("Please enter max spots.")
            return render_template('edit_lot.html', lot=lot)

        
        occupied=lot.max_spots - lot.available
        new_max_spots=int(new_max_spots)
        if new_max_spots< occupied:
            flash('Cannot reduce max spots below currently occupied slots.')
        else:
            if(new_max_spots<lot.max_spots):
                cnt=lot.max_spots-new_max_spots
                for spot in lot.spots:
                    if cnt==0:
                        break
                    if spot.status=='A':
                        db.session.delete(spot)
                        cnt-=1
            else:
                for i in range(new_max_spots-lot.max_spots):
                    db.session.add(ParkingSpot(lot_id=lot.id))        
            lot.max_spots=new_max_spots
            lot.available=new_max_spots-occupied
            
            db.session.commit()
            flash("Lot updated successfully.")
            return redirect(url_for('admin_dashboard'))
    return render_template('edit_lot.html', lot=lot)

@app.route('/user/dashboard')
def user_dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    lots=ParkingLot.query.all()
    reservations=Reservation.query.filter_by(user_id=session['user_id'], leaving_timestamp=None).all()
    histories=History.query.filter_by(user_id=session['user_id']).all()
    return render_template('user_dashboard.html', lots=lots, reservations=reservations,histories=histories)

@app.route('/user/book/<int:lot_id>')
def book_spot(lot_id):
    if not session.get('user_id'):
        return redirect(url_for('login'))
    spot=ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if spot:
        spot.status='O'
        spot.lot.available-=1
        reservation=Reservation(spot_id=spot.id, user_id=session['user_id'])
    
        db.session.add(reservation)
        db.session.commit()
        flash('Spot booked successfully')
    else:
        flash('No available spots in selected lot')
    return redirect(url_for('user_dashboard'))

@app.route('/user/release/<int:res_id>')
def release_spot(res_id):
    reservation=Reservation.query.get(res_id)
    if reservation and reservation.user_id == session.get('user_id'):
        reservation.leaving_timestamp=datetime.utcnow()
        duration=(reservation.leaving_timestamp - reservation.parking_timestamp).total_seconds() / 3600
        reservation.cost=round(duration * reservation.spot.lot.price, 2)
        reservation.spot.status='A'
        reservation.spot.lot.available+=1
        history=History(user_id=session['user_id'],parking_timestamp=reservation.parking_timestamp,leaving_timestamp=reservation.leaving_timestamp,price=reservation.cost)
        db.session.add(history)
        db.session.commit()
        flash(f'Spot released. Cost: ₹{reservation.cost}')
    return redirect(url_for('user_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin123')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
