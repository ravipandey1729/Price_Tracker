l̥# How to Add Products to Track

## Step-by-Step Guide

### 1. Open config.yaml
Open the `config.yaml` file in your text editor.

### 2. Find the Products Section
Scroll down to the `products:` section (around line 79).

### 3. Add Your Product
Copy and paste this template for each new product:

```yaml
  - id: "prod_002"                           # Unique ID (increment: prod_002, prod_003, etc.)
    name: "Product Name Here"                # Full product name
    category: "Electronics"                  # Category (Electronics, Fashion, Home, etc.)
    sku: "PRODUCTSKU"                        # Product SKU/model number
    urls:
      Amazon: "https://www.amazon.com/dp/ASIN"    # Amazon product URL
      eBay: "https://www.ebay.com/itm/ITEMID"     # eBay listing URL (optional)
    alert_threshold:
      percentage_drop: 10                    # Alert when price drops by X%
      target_price: 99.99                    # Alert when price goes below this
```

### 4. Get Product URLs

#### For Amazon:
1. Go to Amazon.com
2. Find the product you want to track
3. Copy the URL from the address bar
4. Extract the ASIN (the part after `/dp/`)
5. Use format: `https://www.amazon.com/dp/YOUR_ASIN_HERE`

**Example:**
- Full URL: `https://www.amazon.com/Sony-WH-1000XM5-Canceling-Headphones-Hands-Free/dp/B09XS7JWHH`
- Shortened: `https://www.amazon.com/dp/B09XS7JWHH`

#### For eBay:
1. Go to eBay.com
2. Find the product listing
3. Copy the URL
4. Format: `https://www.ebay.com/itm/ITEM_NUMBER`

### 5. Example: Adding 3 Products

```yaml
products:
  # Product 1: Headphones
  - id: "prod_001"
    name: "Sony WH-1000XM5 Headphones"
    category: "Electronics"
    sku: "WH1000XM5"
    urls:
      Amazon: "https://www.amazon.com/dp/B09XS7JWHH"
    alert_threshold:
      percentage_drop: 10
      target_price: 299.99

  # Product 2: Laptop
  - id: "prod_002"
    name: "MacBook Air M2"
    category: "Electronics"
    sku: "MACBOOKM2"
    urls:
      Amazon: "https://www.amazon.com/dp/B0B3C2R8MP"
    alert_threshold:
      percentage_drop: 5
      target_price: 999.99

  # Product 3: Phone
  - id: "prod_003"
    name: "iPhone 15 Pro"
    category: "Electronics"
    sku: "IPHONE15PRO"
    urls:
      Amazon: "https://www.amazon.com/dp/B0CHBD39RV"
      eBay: "https://www.ebay.com/itm/123456789"
    alert_threshold:
      percentage_drop: 8
      target_price: 899.99
```

### 6. Important Rules

✅ **DO:**
- Use unique IDs for each product (prod_001, prod_002, etc.)
- Keep proper YAML indentation (2 spaces)
- Use real product URLs from Amazon/eBay
- Set realistic target prices

❌ **DON'T:**
- Use the same ID twice
- Mix tabs and spaces (use spaces only)
- Use invalid URLs
- Forget to save the file

### 7. Validate Your Config

After adding products, run:
```bash
python main.py validate-config
```

This checks for errors in your configuration.

### 8. Initialize Database

After validation, run:
```bash
python main.py init
```

This creates the products in the database.

### 9. Verify Products Appear

Refresh your web dashboard at http://localhost:8000/products to see all your products!

---

## Quick Tips

- **Start small**: Add 2-3 products first, test, then add more
- **Test URLs**: Make sure each URL loads in your browser before adding
- **Use Amazon ASIN**: The product ID in Amazon URLs (after `/dp/`)
- **Categories**: Group similar products together
- **Alert thresholds**: Start with 10% drops, adjust based on experience

## Need Help?

If products don't appear:
1. Check `python main.py validate-config` for errors
2. Check your YAML indentation
3. Make sure URLs are valid
4. Run `python main.py init` after changes
