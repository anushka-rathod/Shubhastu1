# Shubhashtu Fashion - AI Stylist Agent (Vercel AI SDK)

This folder contains the complete, production-ready AI Agent built with the **Vercel AI SDK** (`ai`, `@ai-sdk/react`, `@ai-sdk/google`).

## Features
- **Streaming LLM Chat:** Fast responses with live token streaming using Google Gemini 2.5 Flash / OpenAI GPT-4o.
- **Tool-Calling Architecture:**
  - `searchProducts`: Searches Shubhashtu Fashion's live catalog.
  - `getProductDetails`: Retrieves sizing, care tips, and artisan craftsmanship story.
  - `trackOrder`: Instant order status and BlueDart/Delhivery tracking lookup.
  - `calculateShipping`: Domestic delivery fees and free shipping calculations for Indian PIN codes.
  - `getAvailableCoupons`: Lists promo discounts (`WELCOME10`, `SHUBH500`, `FESTIVE20`).
- **Interactive UI Component:** `ShubhashtuAiStylistWidget` with luxury Indian boutique aesthetics, floating sparkle trigger, and instant product recommendation cards.

## How to Deploy to Vercel
1. Install dependencies:
   ```bash
   pnpm install
   # or npm install
   ```
2. Set Environment Variables in `.env.local`:
   ```env
   GOOGLE_GENERATIVE_AI_API_KEY=your_gemini_api_key
   # or OPENAI_API_KEY=your_openai_api_key
   STORE_URL=https://shubhashtufashion.com
   ```
3. Run locally:
   ```bash
   pnpm dev
   ```
4. Deploy to Vercel:
   ```bash
   vercel
   # or connect your GitHub repository directly to Vercel
   ```

