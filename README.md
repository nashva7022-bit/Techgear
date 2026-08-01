# TechGear

TechGear is a full-featured e-commerce platform for customizable phone cases and laptop accessories, built with Django. The goal was to create something that feels like a real production-ready online store rather than a simple tutorial project. It includes secure Razorpay payments, a wallet system, referrals, coupons and offers, detailed order management, and a fully functional admin panel.

---

# Features

## Customer Features

* Browse products with multiple variants, including color, case type, and device model
* Search and filter products
* Customize products with your own text or image for an additional charge
* Shopping cart and wishlist
* Product reviews restricted to customers who have purchased and received the product
* Checkout using Razorpay, Wallet, Cash on Delivery (COD), or a combination of Wallet and Razorpay
* Coupons and automatic product/category offers, where the highest available discount is applied automatically
* Track orders, cancel or return eligible items, and download invoices
* Referral program where both the referrer and the new customer receive wallet rewards

## Admin Features

* Dashboard displaying revenue, order statistics, best-selling products, and sales charts
* Product, category, inventory, and stock management
* Order processing and return request management
* Configurable referral rewards and other site settings without modifying code
* Export sales reports in PDF and Excel formats

---

# Tech Stack

| Category       | Technology                                 |
| -------------- | ------------------------------------------ |
| Backend        | Python, Django                             |
| Database       | PostgreSQL                                 |
| Payments       | Razorpay                                   |
| Authentication | Email OTP, Google Sign-In (django-allauth) |
| Image Storage  | Cloudinary                                 |
| Frontend       | Tailwind CSS, Bootstrap Icons              |

---

# Project Structure

The project is organized into multiple Django apps, each with a specific responsibility to keep the codebase clean and maintainable.

### users

Manages the custom user model, email-based authentication, addresses, and OTP verification for registration and password reset.

### products

Handles the product catalog.

* `Product` stores the general product information.
* `ProductVariant` stores variant-specific details such as price, stock, color, case type, and device compatibility.
* SKUs are generated automatically to ensure uniqueness.

### orders

The core business logic of the application.

The `services.py` module handles:

* Order placement
* Razorpay payment verification
* Order cancellation
* Return processing
* Refund calculations

Refunds are calculated proportionally based on the customer's original payment method (Wallet, Razorpay, or a combination of both). Since Cash on Delivery payments are collected only upon delivery, COD orders are not refunded electronically.

### store

Handles customer interactions, including:

* Shopping cart
* Wishlist
* Product reviews

Reviews are available only to customers who have successfully purchased and received the product, preventing fake or spam reviews.

### wallet

Implements a digital wallet system.

Instead of simply updating the wallet balance, every credit and debit creates a transaction record, providing a complete transaction history similar to a bank statement.

### coupons

Supports manually entered coupon codes with configurable usage limits and validity periods.

### offers

Provides automatic discounts at both the product and category levels.

If multiple discounts are applicable, the system automatically applies the highest discount available.

### referrals

Each user receives a unique referral code.

* New users receive a wallet bonus immediately after signing up with a valid referral code.
* The referrer receives their reward only after the referred user successfully places their first order.

This approach helps prevent abuse through fake account creation.

### admin_panel & admin_orders

Provides tools for managing the store, including:

* Dashboard
* Product and inventory management
* Order status updates
* Return approvals
* Referral settings
* Other configurable site settings

### reports

Generates sales reports with date-based filtering and supports exporting reports in PDF and Excel formats.

---

# Key Highlights

* Custom user model with email authentication
* OTP-based registration and password reset
* Google Sign-In integration
* Product customization with text and image uploads
* Variant-based inventory management
* Razorpay payment integration
* Digital wallet with complete transaction history
* Split payments using Wallet + Razorpay
* Coupon and offer management
* Referral reward system
* Order cancellation and return workflow
* Automatic refund calculation
* Invoice generation
* Sales analytics dashboard
* PDF and Excel report export
* Responsive UI built with Tailwind CSS

---

# License

This project was built for learning and educational purposes.

This version is more polished, consistent, and GitHub-friendly while still accurately describing your project. It also uses clearer sectioning and wording that will make a stronger impression on recruiters and reviewers.
