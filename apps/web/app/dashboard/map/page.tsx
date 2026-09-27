import { redirect } from "next/navigation";

/**
 * The map workspace merged into the Mission section, so this URL is a plain
 * redirect — old links keep working.
 */
export default function MapPage() {
  redirect("/dashboard");
}
