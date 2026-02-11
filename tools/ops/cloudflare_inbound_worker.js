export default {
    async email(message, env, ctx) {
        const MY_EMAIL = "itti1104@outlook.com";

        // Safety check: Only forward if destination is verified (Cloudflare checks this automatically too)
        try {
            await message.forward(MY_EMAIL);
            console.log(`Forwarded email from ${message.from} to ${MY_EMAIL}`);
        } catch (e) {
            console.error(`Failed to forward email: ${e.message}`);
            message.setReject("Forwarding failed");
        }
    },
};
