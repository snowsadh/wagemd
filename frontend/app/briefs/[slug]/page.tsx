// Renders a generated company brief from Tiger Data.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getBrief } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BriefPage({ params }: { params: { slug: string } }) {
  let brief;
  try {
    brief = await getBrief(params.slug);
  } catch {
    return <p className="text-neutral-500">Could not load this brief. Check the API on :8000.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-neutral-500">
        {brief.company} · {brief.sample_size.toLocaleString()} DOL filings · Updated {brief.last_published.slice(0, 10)}
      </p>
      <article className="prose prose-neutral max-w-none prose-headings:font-normal prose-a:text-signal">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{brief.markdown}</ReactMarkdown>
      </article>
    </div>
  );
}
