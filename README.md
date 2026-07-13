# TechGear

TechGear is an e-commerce platform I built for customizable phone cases and laptop accessories. It's a Django project, and the goal was to make it feel like a real production store rather than a tutorial project — so it has actual Razorpay payments, a wallet system, referrals, coupons/offers, and a proper admin panel behind it, not just a basic cart-and-checkout demo.

## Features

Customer side:
- Browse products with variants (color, case type, device model), filter and search
- Customize products with your own text or image, for an extra fee
- Cart, wishlist, and reviews (only if you've actually bought and received the product)
- Checkout with Razorpay, wallet, or a split of the two — plus COD
- Coupons and automatic offers at product/category level (whichever discount is bigger wins)
- Track orders, cancel or return items, download invoices
- Refer friends and both of you get wallet credit

Admin side:
- Dashboard with revenue, orders, best sellers, and a sales chart
- Manage products, categories, inventory, and stock
- Handle order status changes and return requests
- Configure site settings and the referral program without touching code
- Export sales reports as PDF or Excel

## Tech Stack

Backend is Python/Django, database is PostgreSQL. Payments run through Razorpay, images are hosted on Cloudinary, and login supports both email/OTP and Google SSO via django-allauth. Frontend is Tailwind CSS with Bootstrap icons — kept it simple, no heavy JS framework since it didn't need one.



## How the project is organized

I split things into separate Django apps by responsibility instead of dumping everything into one. Quick rundown of each:

**users** — custom user model (login by email), addresses, and the OTP flow for signup/password reset.

**products — the catalogue itself. `Product` holds the general info, `ProductVariant` is where price/stock/color/case-type actually live, and SKUs are auto-generated so I never have to worry about collisions.

**orders** — this is the biggest and most important app. `services.py` has basically all the money logic: placing orders, verifying Razorpay payments, cancellations, and returns. Refunds are proportional to what was actually paid (wallet vs Razorpay vs COD), which took some thought to get right — COD never gets refunded since no cash was collected yet.

**store** — cart, wishlist, and reviews. Reviews are locked to people who've actually received the product, so there's no fake review problem.

**wallet** — a simple balance plus a full transaction log. Every credit or debit creates a record, so it works like an actual bank statement rather than just a number that changes.

**coupons** and **offers** — coupons are manually entered codes with usage limits; offers are automatic discounts on a product or a whole category. If both apply, the bigger discount wins.

**referrals** — every user gets a shareable code. New signups get an instant wallet bonus; the person who referred them only gets paid once the new user actually places an order. I did it this way on purpose — paying the referrer immediately on signup would make it too easy to farm fake accounts for free wallet money.

**admin_panel** and **admin_orders** — this is where the store gets managed day to day: dashboard, inventory, order status changes, return approvals, and site-wide settings (like the referral reward amounts) that don't require a code change.

**reports** — sales reports with date filtering, and export to PDF or Excel for anyone who wants the numbers outside the app.

## License

Built for learning