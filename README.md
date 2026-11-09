# Yunqida Energy Kenya – Django website

## Run it
```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_products   # loads 6 sample products
python manage.py createsuperuser
python manage.py runserver
```
Open http://127.0.0.1:8000  ·  Admin: http://127.0.0.1:8000/admin

## Things to replace before launch
| What | Where |
|---|---|
| Official logo | Overwrite `static/img/logo.svg` (colour, for white backgrounds) and `static/img/logo-light.svg` (white version for the dark footer). PNG works too: change the filenames in `core/templates/core/base.html`. |
| Phone, email, address, WhatsApp | `core/context_processors.py` (one place, updates every page) |
| Where enquiry emails go | `ENQUIRY_NOTIFY_TO` in `config/settings.py` |
| Product specs | Admin > Products (spec values in the seed data are placeholders) |
| Product photos | Admin > Products > Image (falls back to the illustration if empty) |
| Hero video | `static/video/yunqida.mp4` (keep it under ~5 MB, muted, H.264) |
| Section images | `static/img/*.svg`. Replace with photos and update the `<img>` tags in `home.html` / `solutions.html` |

## Enquiries
Every form submission is saved in Admin > Enquiries (tick "handled" when done) and emailed to `ENQUIRY_NOTIFY_TO`.
In development emails print to the terminal. For production add SMTP settings.

## Going live checklist
- `DEBUG = False`, set `ALLOWED_HOSTS = ['yourdomain.co.ke']`, move `SECRET_KEY` to an environment variable
- `python manage.py collectstatic`, then serve static files with Nginx or WhiteNoise
- Serve `/media/` (product uploads) from your web server
- Set up SMTP and HTTPS

## Structure
```
config/            settings, root urls
core/              models (Product, Enquiry), views, forms, admin
core/templates/    base.html + home, about, solutions, products, product_detail, contact
static/css|js|img|video
```
