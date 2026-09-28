import { redirect } from "next/navigation";

/**
 * The Mission Console lives at /dashboard now; this URL is a plain redirect
 * so old links and bookmarks keep working.
 */
export default function ConsolePage() {
  redirect("/dashboard");
}
