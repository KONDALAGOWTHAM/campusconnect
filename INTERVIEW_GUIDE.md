# CampusConnect interview guide

## 60-second introduction

CampusConnect helps students buy and sell used items within their college communities. Buyers can search by campus, price, category and condition. Sellers can publish photos, manage availability and respond to private messages. I used Django because it gives me database models, authentication, forms, templates and an admin panel in one framework. The main engineering work was making permissions apply on the server, validating uploaded images and preventing duplicates with database constraints. The app runs locally with SQLite. Its Render configuration uses PostgreSQL, Gunicorn, WhiteNoise and persistent S3-compatible image storage.

## Two-minute explanation

Students often have unused textbooks or equipment, while other students need the same items at a lower price. CampusConnect lets someone find an item, open its listing and contact the seller to plan a public campus meetup. Students can buy and sell from the same account. Email confirmation shows that a user can receive mail at their address. College affiliation is self-reported.

A Django view handles each route. It checks permissions, uses a form to validate input and calls the ORM to read or write data. The resulting page is rendered on the server. The marketplace uses paginated search, and listing cards fetch related data up front. Models connect each product to its owner, campus, images and conversations. The database prevents duplicate favorites and duplicate conversations, even when two requests reach the server.

I checked authorization in the backend because hiding links does not protect a URL. Each image is checked, resized and saved under a random WebP filename. Messages store both the sender and the read timestamp. The inbox updates through lightweight polling, which keeps deployment simple. Administrators can review reports and remove products using model permissions. Dashboard metrics come from database queries, and the included demo accounts make it easy to demonstrate both sides of a transaction.

## Design decisions to explain

- **Why Python and Django?** Python keeps the code readable. Django supplies authentication, migrations, forms, template escaping and admin features.
- **How do CRUD and permissions work?** A verified account can publish. Public views query visible products. An owner can edit status or delete an eligible listing. Staff with the right permission can moderate it.
- **How do images reach storage?** The form checks bytes, size, format and dimensions, then Pillow writes resized WebP. Django writes it to local storage or the private S3 bucket.
- **How do messages work?** A thread connects a product, seller and buyer. Messages attach to that thread, and the participants check it periodically over HTTP.
- **What was challenging?** A listing, its images, its availability and its permissions must agree. A row lock protects concurrent edits on PostgreSQL, form validation checks combined uploaded and retained photos, and database constraints enforce uniqueness.

## 30 technical questions

| # | Question | Short answer |
| --- | --- | --- |
| 1 | What problem does CampusConnect solve? | It helps students find and sell used items around their college. |
| 2 | Why Python? | It has readable syntax and strong libraries for web development and images. |
| 3 | Why Django? | It includes secure authentication, forms, an ORM and an admin panel. |
| 4 | What is MVT? | Models store data, views handle requests and templates render HTML. |
| 5 | What does the ORM do? | It turns Python database operations into SQL. |
| 6 | What is a migration? | A versioned database schema change. |
| 7 | Why make a custom user model? | To sign in by email and store student profile fields. |
| 8 | How are passwords stored? | Django stores salted hashes and checks the hash when a user signs in. |
| 9 | What does email confirmation prove? | The account holder had access to that email inbox. |
| 10 | How does email confirmation expire? | The signed token has a timestamp and becomes invalid after the configured lifetime or an account change. |
| 11 | What does CRUD stand for? | Create, read, update and delete. |
| 12 | How do you stop users editing each other's items? | The edit and status views look up the product with the signed-in user as its seller. |
| 13 | How do you stop staff from accessing unavailable operations? | Django Admin checks model permissions for views and actions. |
| 14 | What is CSRF? | It is when another site tries to make the user's browser send an unwanted request. |
| 15 | How do you reduce XSS? | Django templates escape user text, and messages are rendered with those templates. |
| 16 | What happens when an image is uploaded? | The server validates it, resizes it and encodes it as WebP. |
| 17 | Why generate the image filename? | Random keys avoid collisions and remove dependence on a user's supplied filename. |
| 18 | What makes a listing public? | It has an active or reserved status and belongs to an active account. |
| 19 | How does search work? | The ORM checks title and description substrings, then applies the selected filters. |
| 20 | How are filters kept on the next page? | Pagination links copy the filter query string and update the page parameter. |
| 21 | What is an N+1 query? | A list query is followed by another query for every row to fetch related data. |
| 22 | When do you use `select_related`? | For single related rows, such as each listing's seller or category. |
| 23 | When do you use `prefetch_related`? | For related sets, such as all photos attached to a group of listings. |
| 24 | What prevents duplicate wishlists? | A unique database constraint on the user and product pair. |
| 25 | How does a conversation stay private? | Every thread request checks that the signed-in user is the buyer or seller. |
| 26 | How do unread counts work? | The inbox counts incoming messages whose read timestamp is empty. |
| 27 | How are messages refreshed? | The browser fetches the latest rendered messages periodically while the thread is visible. |
| 28 | Where do dashboard numbers come from? | ORM counts, sums and grouped queries for the signed-in user. |
| 29 | Why use PostgreSQL for production? | It provides durable managed storage and supports concurrent requests and row locks. |
| 30 | What do Gunicorn and WhiteNoise do? | Gunicorn runs the Django application, and WhiteNoise serves versioned static files. |
