import { EmailMessage } from "cloudflare:email";

export default {
    async fetch(request, env) {
        if (request.method !== "POST") {
            return new Response("Method Not Allowed", { status: 405 });
        }

        try {
            const payload = await request.json();
            const { to, subject, body } = payload;

            if (!to || !subject || !body) {
                return new Response("Missing required fields: to, subject, body", { status: 400 });
            }

            const sender = "luka.ai@theedges.work";
            const messageId = `<${crypto.randomUUID()}@theedges.work>`;
            const timestamp = new Date().toUTCString();

            // Use CRLF (\r\n) for email headers/body separation as per RFC 822/5322
            const rawEmail = `From: Luka AI <${sender}>\r
To: ${to}\r
Subject: ${subject}\r
Message-ID: ${messageId}\r
MIME-Version: 1.0\r
Content-Type: text/plain; charset=utf-8\r
Date: ${timestamp}\r
\r
${body}`;

            const message = new EmailMessage(
                sender,
                to,
                rawEmail
            );

            await env.EMAIL.send(message);

            return new Response("Email sent successfully via Cloudflare Email Routing", {
                status: 200,
                headers: { "content-type": "application/json" },
            });
        } catch (e) {
            return new Response(JSON.stringify({ error: e.message }), {
                status: 500,
                headers: { "content-type": "application/json" },
            });
        }
    },
};
