// Methodology for the filing-backed salary index.
export default function AboutPage() {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-normal tracking-tight">Methodology</h1>
      <p className="text-neutral-600">
        WAGE.md is built from US Department of Labor PERM and H1B LCA disclosures — offered wages
        sponsoring employers report by job title. Unlike crowdsourced sources, every number
        traces to a federal case number.
      </p>
      <ul className="list-disc pl-5 text-neutral-600">
        <li>Source: DOL FLAG quarterly disclosures + state WARN Act portals.</li>
        <li>Titles normalized to a canonical role/level taxonomy (never guessed).</li>
        <li>Distributions and company briefs stored in Tiger Data and served in the Index.</li>
      </ul>
      {/* TODO(frontend): expand with the Levels.fyi vs DOL comparison from the demo script. */}
    </div>
  );
}
