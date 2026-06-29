TechGear Project
My first full-stack project

TechGear is a Django-based e-commerce platform for phone and laptop accessories. Customers can browse and filter products by category, brand, device model, and price, then select variants by colour and case type. Products support personalization — customers can add custom text or upload an image before adding to cart. Orders can be placed via Razorpay or Cash on Delivery, with an optional wallet deduction at checkout. The wallet can be topped up anytime via Razorpay and receives automatic refunds on cancellations and approved returns.
 
User accounts are email-based with OTP verification and Google SSO support. Each user gets a profile dashboard to manage their addresses, track orders, cancel individual items, request returns, and leave reviews on delivered products. Coupons with percentage or fixed discounts can be applied at checkout, with per-user usage enforcement and configurable validity dates and order minimums.
 
The admin panel is fully custom — no Django admin. It includes a live dashboard with revenue charts, best-selling products, categories, and brands. Admins can manage orders through defined status transitions, approve or reject return requests, update inventory, create product and category-level discount offers, manage coupons, view wallet balances, and manually credit users. Every admin action is recorded in an activity log.
Stack: Python, Django, PostgreSQL, Razorpay, Cloudinary, django-allauth, Tailwind CSS, WeasyPrint.