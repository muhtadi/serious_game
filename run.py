from app import create_app, db

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # host='0.0.0.0' agar bisa diakses dari semua perangkat di jaringan lokal
    # port=5000 bisa diganti sesuai kebutuhan
    app.run(host='0.0.0.0', port=5000, debug=False)
