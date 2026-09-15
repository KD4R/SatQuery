import { ReportScreen } from "../../../../components/report/ReportScreen";

export const metadata = { title: "Report — SatQuery AI" };

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReportScreen missionId={id} />;
}
