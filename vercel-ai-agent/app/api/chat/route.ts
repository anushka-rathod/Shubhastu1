import { streamText, tool } from 'ai';
import { google } from '@ai-sdk/google';
import { z } from 'zod';

// Allow streaming responses up to 60 seconds
export const maxDuration = 60;

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: google('gemini-2.5-flash'),
    system: `You are the official AI Fashion Stylist & Concierge for SHUBHASHTU FASHION ("Style That Speaks for You.").
Your role is to guide customers with elegance, warmth, and expert knowledge of handcrafted Indian jewelry and hand-painted apparel.

Brand Guidelines:
- Heritage Earrings: Royal Kundan Chandbalis, Mayura Temple Dancing Peacock Jhumkas, Freshwater Pearls, Afghani Tribal Silver. 24K gold micron plating, hypoallergenic brass.
- Hand-Painted T-Shirts: 100% hand-painted with permanent mineral colors on 220 GSM bio-washed combed cotton. Pre-shrunk luxury streetwear cut.
- Free delivery across India on orders above ₹999.
- Use your tools to search products, track orders, check shipping, and share discount coupons.`,
    messages,
    tools: {
      searchProducts: tool({
        description: 'Search the Shubhashtu Fashion catalog for earrings, hand-painted t-shirts, kurtis, or accessories with real-time stock and prices.',
        parameters: z.object({
          query: z.string().optional().describe('Search query keyword like kundan, peacock, mandala, temple, jhumka'),
          category: z.enum(['earrings', 'hand-painted-t-shirts', 'ethnic-and-kurtis', 'accessories', 'all']).optional(),
          maxPrice: z.number().optional().describe('Maximum budget in INR')
        }),
        execute: async ({ query, category, maxPrice }) => {
          // Live API endpoint from your store
          const baseUrl = process.env.STORE_URL || 'https://shubhashtufashion.vercel.app';
          const params = new URLSearchParams();
          if (query) params.append('q', query);
          if (maxPrice) params.append('max_price', maxPrice.toString());

          const res = await fetch(`${baseUrl}/api/search?${params.toString()}`);
          const products = await res.json();
          return { products: products.slice(0, 4) };
        }
      }),

      getProductDetails: tool({
        description: 'Get in-depth specifications, sizing options, fabric care instructions, and artisan story for a specific product.',
        parameters: z.object({
          slug: z.string().describe('Product slug identifier, e.g. kundan-meenakari-royal-chandbali-earrings')
        }),
        execute: async ({ slug }) => {
          return {
            slug,
            careTip: 'Store in airtight velvet pouch. Keep away from perfumes and liquids.',
            shipping: 'Dispatches within 24 hours via express air couriers.'
          };
        }
      }),

      trackOrder: tool({
        description: 'Track real-time shipment status, courier name, tracking number, and delivery date for a customer order.',
        parameters: z.object({
          orderNumber: z.string().describe('Shubhashtu order number, e.g. SHB-2026-1001')
        }),
        execute: async ({ orderNumber }) => {
          const baseUrl = process.env.STORE_URL || 'https://shubhashtufashion.vercel.app';
          const res = await fetch(`${baseUrl}/api/track?order_number=${encodeURIComponent(orderNumber)}`);
          if (!res.ok) {
            return { found: false, message: `Order #${orderNumber} not found.` };
          }
          return await res.json();
        }
      }),

      calculateShipping: tool({
        description: 'Calculate domestic delivery charge, estimated transit days, and serviceability for an Indian PIN code.',
        parameters: z.object({
          pincode: z.string().describe('6-digit Indian postal PIN code'),
          orderValue: z.number().describe('Estimated order subtotal in INR')
        }),
        execute: async ({ pincode, orderValue }) => {
          const baseUrl = process.env.STORE_URL || 'https://shubhashtufashion.vercel.app';
          const res = await fetch(`${baseUrl}/api/shipping/calculate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pincode, subtotal: orderValue })
          });
          return await res.json();
        }
      }),

      getAvailableCoupons: tool({
        description: 'List active promotional discount coupons, minimum order values, and percentage savings.',
        parameters: z.object({}),
        execute: async () => {
          return {
            coupons: [
              { code: 'WELCOME10', discount: '10% OFF', description: 'New customer welcome discount' },
              { code: 'SHUBH500', discount: 'Flat ₹500 OFF', description: 'On orders above ₹2,499' },
              { code: 'FREESHIP', discount: 'Free Shipping', description: 'Free domestic express delivery' },
              { code: 'FESTIVE20', discount: '20% OFF', description: 'Festive season discount above ₹1,999' }
            ]
          };
        }
      })
    }
  });

  return result.toDataStreamResponse();
}

