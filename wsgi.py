from app import create_app, init_db

app = create_app()

with app.app_context():
    init_db(app)

if __name__ == "__main__":
    app.run()
