# Costa Coffee Menu Page Structure Documentation

**URL:** https://www.costa.co.uk/menu  
**Date:** February 23, 2026

This document describes the DOM structure and interactive elements on the Costa Coffee menu page based on the working Selenium scraper in `3_CostaCoffee_selenium.py`.

---

## 1. Cookie Banner

**Action Required:** Accept cookies before interacting with the menu

**Selectors:** Handled by `try_click_accept_cookies(driver)` helper function

---

## 2. Top-Level Navigation Tabs

### Drinks Tab

- **Text:** "Drinks"
- **Element Type:** `<button>` or `<a>` or element with `role="tab"`
- **Selection Strategy:**
  ```python
  # XPath with case-insensitive matching
  "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'drinks')]"
  "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'drinks')]"
  "//*[@role='tab'][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'drinks')]"
  ```
- **Click Method:** JavaScript click via `safe_click()` to avoid interception

### Food Tab

- **Text:** "Food"
- **Element Type:** `<button>` or `<a>` or element with `role="tab"`
- **Selection Strategy:** Same patterns as Drinks tab, using 'food' instead
- **Click Method:** JavaScript click via `safe_click()`

### JavaScript Fallback Selector

When standard Selenium clickability checks fail:

```javascript
const nodes = [
  ...document.querySelectorAll("button,a,[role='tab'],[role='button']"),
];
for (const n of nodes) {
  const text = (n.innerText || n.textContent || '').trim().toLowerCase();
  const style = window.getComputedStyle(n);
  if (!text || style.display === 'none' || style.visibility === 'hidden')
    continue;
  if (text === target || text.includes(target)) return n;
}
```

---

## 3. Subcategory Filter Buttons

After clicking a main tab (Drinks or Food), subcategory buttons appear.

### CSS Selectors (tried in order)

```css
[class*='ubcategory'] button
[class*='ilter'] button
[class*='ategory'] button
[class*='tab'] button
button[aria-controls]
button[aria-selected]
```

### Characteristics

- **Element Type:** `<button>`
- **Visibility:** Must be `is_displayed() == True`
- **Valid Subcategories:** Have 2+ visible buttons matching the selector
- **Text Length:** Between 3-40 characters

### Known Subcategory Names (Examples)

Under **Drinks**:

- "Hot Drinks"
- "Cold Drinks"
- "Coffee"
- "Tea"
- "Iced"
- "Speciality"

Under **Food**:

- "Breakfast"
- "Lunch"
- "Snacks"
- "Sweet Treats"
- "Savoury"

### Excluded Patterns (Not Subcategories)

The scraper filters out these button texts (lowercase):

- Exact matches: "drinks", "food", "all drinks", "our menu", "order now", "nutrition", "allergens", "vegetarian", "vegan", "clear", "show full allergens list", "milk", "tree nut", "peanut", "soybeans", "sesame", "gluten", "eggs", "sulphites", "contact us", "about us", "for business"
- Contains: "costa club", "gift cards", "sustainability", "press", "careers", "privacy", "cookie", "terms", "store dietary", "branded products", "ready to drink", "costa express", "costa at home", "business inquiries", "download our app"

---

## 4. Product Cards

After selecting a subcategory, product cards are displayed on the page.

### CSS Selectors (tried in order)

```css
div[role='button']
[class*='roduct'][class*='ard']
[class*='roduct'][class*='ile']
a[class*='roduct']
```

### Structure

- **Container:** `<div role="button">` or similar
- **Image:** Contains an `<img>` tag
- **Product Name:** Extracted from `img` tag's `alt` attribute
- **Fallback:** If no image/alt, use first line of `element.text`

### Example HTML Pattern

```html
<div role="button" class="ProductCard">
  <img alt="Flat White" src="..." />
  <!-- Other content -->
</div>
```

### Lazy Loading

Products may be lazy-loaded. The scraper scrolls to trigger loading:

```python
def scroll_to_load_all(driver, scrolls=8, pause=0.6):
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, 800);")
        sleep(pause)
    driver.execute_script("window.scrollTo(0, 0);")
    sleep(WAIT_SHORT)
```

### Excluded Product Names (Noise Filtering)

Product cards with these text patterns are ignored:

- "account menu"
- "costa club"
- "gift cards"
- "exclusive rewards"
- "birthday"
- "download our app"
- "contact us"
- "about us"

---

## 5. Product Detail Modal

Clicking a product card opens a modal/overlay with detailed information.

### Modal Container Selectors (tried in order)

```css
[role='dialog']
[class*='Modal']
[class*='modal']
[class*='roductView']
[class*='roductDetail']
[class*='etail']
```

### Modal Characteristics

- **Type:** Overlay modal (not a new page)
- **Must be visible:** `is_displayed() == True`
- **Must have content:** `len(element.text.strip()) > 20`
- **Wait Strategy:** `WebDriverWait(driver, 10)` for modal presence

---

## 6. Product Information in Modal

### A. Product Description

**Location:** Near the top of the modal

**CSS Selectors (tried in order):**

```css
[class*='escription']
[class*='ummary']
p
```

**Characteristics:**

- Plain text, usually 1-3 sentences
- Length > 10 characters

---

### B. Ingredients

**Location:** Inside an expandable accordion section

**Accordion Button:**

- **Text:** Contains "ingredient" (case-insensitive)
- **Element:** `<button>`
- **XPath:**
  ```xpath
  .//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ingredient')]
  ```

**Content Selector:**

```css
[class*='ngredient']
```

**Expansion Strategy:**

1. Find button containing "ingredient"
2. Click it via JavaScript (`safe_click()`)
3. Wait 0.5s for accordion to expand
4. Extract text from container matching `[class*='ngredient']`

---

### C. Nutrition Information

**Location:** Inside an expandable accordion section (may be initially collapsed)

**Accordion Buttons:**

- **Text:** Contains "nutrition" or "nutritional" (case-insensitive)
- **Element:** `<button>`
- **XPath:**
  ```xpath
  .//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nutrition')]
  .//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nutritional')]
  ```

**Table Structure:**

```html
<table>
  <tr>
    <td>Energy (kJ)</td>
    <td>123</td>
    <!-- Per 100g/ml -->
    <td>456</td>
    <!-- Per Portion -->
  </tr>
  <tr>
    <td>Energy (kcal)</td>
    <td>29</td>
    <td>108</td>
  </tr>
  <!-- More rows... -->
</table>
```

**Extraction Strategy:**

1. Expand accordion by clicking button with "nutrition"
2. Find all `<tr>` elements in modal
3. For each row:
   - Column 0 (`td[0]`): Nutrient name (e.g., "Energy (kJ)")
   - Column 1 (`td[1]`): Value per 100g/ml
   - Column 2 (`td[2]`): Value per portion (if present)

**Known Nutrition Fields:**

- Energy (kJ) - Per 100g/ml, Per Portion
- Energy (kcal) - Per 100g/ml, Per Portion
- Fat (g) - Per 100g/ml, Per Portion
- of which is saturates (g) - Per 100g/ml, Per Portion
- Carbohydrate (g) - Per 100g/ml, Per Portion
- of which is sugars (g) - Per 100g/ml, Per Portion
- Protein (g) - Per 100g/ml, Per Portion
- Salt (g) - Per 100g/ml, Per Portion
- Vitamin C (mg) - Per 100g/ml, Per Portion (some items)
- Vitamin B6 (mg) - Per 100g/ml, Per Portion (some items)
- Zinc (mg) - Per 100g/ml, Per Portion (some items)

**Regex Fallback (if table parsing fails):**

```python
patterns = [
    (r"Energy\s*\(kJ\)\s+([\d.]+)\s+([\d.]+)", "Energy (kJ)"),
    (r"Energy\s*\(kcal\)\s+([\d.]+)\s+([\d.]+)", "Energy (kcal)"),
    (r"Fat\s*\(g\)\s+([\d.]+)\s+([\d.]+)", "Fat (g)"),
    # ... etc
]
```

---

### D. Allergen Information

**Location:** Inside an expandable accordion section

**Accordion Button:**

- **Text:** Contains "allergen" (case-insensitive)
- **Element:** `<button>`
- **XPath:**
  ```xpath
  .//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allergen')]
  ```

**Content Selectors:**

```css
[class*='llergen']
[class*='llergie']
```

**Alternative XPaths:**

```xpath
.//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contains:')]
.//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'allergen')]
```

**Format:**

- Usually a text block listing allergens
- May start with "Contains:" followed by allergen list
- Example: "Contains: Milk, Soya, Gluten (Wheat)"

---

## 7. Closing the Modal

### Close Button Selectors (tried in order)

```css
button[aria-label*='lose']
button[class*='lose']
```

**XPath:**

```xpath
//button[contains(@class, 'close') or contains(@class, 'Close')]
```

**Additional Fallback Selectors:**

```css
[class*='Modal'] button:first-child
[role='dialog'] button
```

### Close Strategies

1. Find and click close button via JavaScript (`safe_click()`)
2. If no button found: Press ESC key
   ```python
   driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
   ```

### Wait After Closing

- Short wait (1.0s) after closing to allow DOM to reset

---

## 8. Important Implementation Notes

### Stale Element Prevention

The scraper re-queries the product list on each iteration:

```python
for idx in range(total):
    fresh_cards = find_product_cards(driver)  # Re-query
    if idx >= len(fresh_cards):
        break
    card = fresh_cards[idx]
```

### Safe Click Implementation

To avoid `ElementClickInterceptedException`:

```python
def safe_click(driver, element):
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", element
    )
    sleep(0.3)
    driver.execute_script("arguments[0].click();", element)
```

### Wait Times

```python
WAIT_SHORT = 1.0   # After closing modals, short actions
WAIT_MEDIUM = 2.0  # After clicking subcategories
WAIT_LONG = 5.0    # After clicking main tabs, initial page load
```

### Page Load Timeout

```python
driver.set_page_load_timeout(90)  # 90 seconds
```

---

## 9. Complete Scraping Flow

```
1. Navigate to https://www.costa.co.uk/menu
2. Accept cookie banner (via helper function)
3. Wait WAIT_LONG (5s)

For each tab in ["Drinks", "Food"]:
    4. Click tab button (Drinks or Food)
    5. Wait WAIT_LONG (5s)
    6. Find subcategory buttons

    For each subcategory:
        7. Click subcategory button
        8. Wait WAIT_MEDIUM (2s)
        9. Scroll to load all products (lazy loading)
        10. Find all product cards

        For each product:
            11. Click product card
            12. Wait for modal to appear (10s timeout)
            13. Wait WAIT_MEDIUM (2s)
            14. Expand nutrition accordion (if present)
            15. Expand allergen accordion (if present)
            16. Expand ingredient accordion (if present)
            17. Extract all data from modal
            18. Close modal
            19. Wait WAIT_SHORT (1s)
```

---

## 10. Known Issues & Solutions

### Issue: ElementClickInterceptedException

**Solution:** Use JavaScript click (`driver.execute_script("arguments[0].click();", element)`)

### Issue: Stale Element Reference

**Solution:** Re-query elements before each interaction

### Issue: Modal doesn't appear

**Solution:** Implemented in scraper with fallback to close and continue

### Issue: Lazy-loaded products not appearing

**Solution:** Scroll down 8 times with 0.6s pauses to trigger loading

### Issue: Accordion sections initially collapsed

**Solution:** Explicitly click accordion buttons before extracting content

---

## 11. Example HTML Patterns (Pseudocode)

```html
<!-- Main Navigation -->
<nav>
  <button role="tab">Drinks</button>
  <button role="tab">Food</button>
</nav>

<!-- Subcategory Filters -->
<div class="subcategory-filters">
  <button aria-selected="true">Hot Drinks</button>
  <button aria-selected="false">Cold Drinks</button>
  <!-- ... more subcategories -->
</div>

<!-- Product Grid -->
<div class="product-grid">
  <div role="button" class="ProductCard">
    <img alt="Flat White" src="..." />
    <span>Flat White</span>
  </div>
  <!-- ... more products -->
</div>

<!-- Product Modal -->
<div role="dialog" class="Modal">
  <button aria-label="Close" class="CloseButton">×</button>

  <h2>Flat White</h2>
  <p class="Description">Smooth and velvety...</p>

  <button>Ingredients</button>
  <div class="IngredientSection">Milk, Coffee</div>

  <button>Nutrition</button>
  <div class="NutritionSection">
    <table>
      <tr>
        <td>Energy (kcal)</td>
        <td>29</td>
        <td>108</td>
      </tr>
      <!-- ... -->
    </table>
  </div>

  <button>Allergens</button>
  <div class="AllergenSection">Contains: Milk</div>
</div>
```

---

## 12. Testing Checklist

- [ ] Cookie banner is accepted
- [ ] Both "Drinks" and "Food" tabs are clickable
- [ ] Subcategory buttons are detected and clickable
- [ ] Products are loaded after scrolling
- [ ] Product cards open modals on click
- [ ] Product name is extracted from image alt text
- [ ] Accordion sections (Nutrition, Allergens, Ingredients) expand
- [ ] Nutrition table is parsed correctly (2 or 3 columns)
- [ ] Modal closes via close button or ESC key
- [ ] No duplicate products are scraped
- [ ] All data is saved to JSON and CSV

---

**End of Documentation**
