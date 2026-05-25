import argparse
import html
import json

from utils import TOOL_DISCLAIMER, validate_report_schema

# P2-2: Human-readable status labels
STATUS_LABELS = {
    "CONFIRMED": "Confirmed Discrepancy",
    "FALSE_POSITIVE": "Dismissed",
    "PENDING": "Awaiting Review",
    "DISPUTED": "Under Dispute",
    "IN_PROGRESS": "Review In Progress",
}

# P2-2: Badge color mapping
BADGE_COLORS = {
    "CONFIRMED": "bg-red-100 text-red-800",
    "PENDING": "bg-yellow-100 text-yellow-800",
    "DISPUTED": "bg-orange-100 text-orange-800",
    "IN_PROGRESS": "bg-blue-100 text-blue-800",
    "FALSE_POSITIVE": "bg-green-100 text-green-800",
}
DEFAULT_BADGE_COLOR = "bg-gray-100 text-gray-600"

# P0-11: Allowlist for RoB colors
ROB_COLOR_ALLOWLIST = {"green", "yellow", "red", "gray"}


class HTMLReporter:
    def __init__(self, report_path: str, output_html_path: str):
        self.report_path = report_path
        self.output_html_path = output_html_path
        self.report_data = self._load_report()

    def _load_report(self) -> dict:
        try:
            with open(self.report_path, encoding='utf-8') as f:
                data = json.load(f)
            validate_report_schema(data)
            return data
        except Exception as e:
            print(f"Error loading report for HTML generation: {e}")
            return {}

    def generate(self):
        if not self.report_data:
            return

        nct_id = html.escape(str(self.report_data.get("nctId", "Unknown")))
        citation = html.escape(str(self.report_data.get("citation", "Unknown")))
        status = html.escape(str(self.report_data.get("discrepancy_results", {}).get("status", "UNKNOWN")))
        discrepancies = self.report_data.get("discrepancy_results", {}).get("discrepancies", [])
        rob_data = self.report_data.get("rob_assessment", {
            "score": "Not Assessed",
            "color": "gray",
            "justification": "No automated RoB assessment data found."
        })

        rob_score = html.escape(str(rob_data.get("score", "Unknown")))
        rob_color = str(rob_data.get("color", "gray"))
        # P0-11: Validate rob_color against allowlist
        if rob_color not in ROB_COLOR_ALLOWLIST:
            rob_color = "gray"
        rob_color = html.escape(rob_color)
        rob_score_initial = rob_score[0] if rob_score else "?"
        rob_color_class = f"bg-{rob_color}-500" if rob_color != "yellow" else "bg-yellow-400"

        status_color = "bg-red-100 text-red-800 border-red-200" if status == "WARNING" else "bg-green-100 text-green-800 border-green-200"

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Integrity Report: {nct_id}</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                body {{ font-family: 'Inter', sans-serif; background-color: #f9fafb; }}
                .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border-width: 0; }}
            </style>
        </head>
        <body class="p-8">
            <div class="max-w-5xl mx-auto">
                <header class="mb-8 flex justify-between items-end">
                    <div>
                        <h1 class="text-3xl font-bold text-gray-900">Evidence Integrity Report</h1>
                        <p class="text-gray-600 mt-2">Analyzed against ClinicalTrials.gov Protocol</p>
                    </div>
                    <div class="text-right">
                        <span class="px-4 py-2 rounded-full font-semibold border {status_color}">
                            STATUS: {status}
                        </span>
                    </div>
                </header>

                <div class="bg-white rounded-lg shadow p-6 mb-8 border border-gray-200">
                    <h2 class="text-xl font-semibold mb-4 border-b pb-2">Study Details</h2>
                    <p><strong>NCT ID:</strong> <a href="https://clinicaltrials.gov/study/{nct_id}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:underline">{nct_id}</a></p>
                    <p class="mt-2"><strong>Publication:</strong> {citation}</p>
                    <p class="mt-2 text-sm text-gray-500">Generated on: {html.escape(str(self.report_data.get('timestamp', '')))}</p>
                </div>

                <!-- Cochrane RoB 2.0 Mapping -->
                <div class="bg-white rounded-lg shadow p-6 mb-8 border border-gray-200">
                    <h2 class="text-xl font-semibold mb-4 border-b pb-2">Cochrane Risk of Bias 2.0 (Domain 5 Mapping)</h2>
                    <div class="flex items-center gap-6">
                        <div class="w-20 h-20 rounded-full flex items-center justify-center border-4 border-gray-100" id="rob-traffic-light">
                            <div class="w-16 h-16 rounded-full {rob_color_class} shadow-inner flex items-center justify-center text-white font-bold text-2xl">
                                {rob_score_initial}
                            </div>
                        </div>
                        <div class="flex-1">
                            <h3 class="text-lg font-bold text-gray-800">Domain 5: Bias in selection of the reported result</h3>
                            <p class="mt-1 text-gray-600"><strong>Assessment:</strong> {rob_score}</p>
                            <p class="mt-2 text-sm text-gray-500 italic">"Bias in the selection of the reported result arises when outcomes or analyses are reported based on the findings."</p>
                        </div>
                    </div>
                </div>

                <!-- Consensus Status Table -->
                <div class="bg-white rounded-lg shadow p-6 mb-8 border border-gray-200">
                    <h2 class="text-xl font-semibold mb-4 border-b pb-2">Human-AI Consensus Overview</h2>
                    <table class="min-w-full divide-y divide-gray-200 text-sm">
                        <caption class="sr-only">Summary of discrepancy review statuses</caption>
                        <thead class="bg-gray-50">
                            <tr>
                                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Discrepancy</th>
                                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AI Confidence</th>
                                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Consensus Status</th>
                                <th scope="col" class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Reviewers</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
        """
        for d in discrepancies:
            d_measure = html.escape(str(d.get('publication_outcome') or d.get('protocol_outcome', 'Unknown')))
            d_conf = f"{round(d.get('confidence', 1.0) * 100)}%"
            d_cons_raw = str(d.get('consensus_status', 'PENDING'))
            d_cons = html.escape(d_cons_raw)
            d_cons_label = html.escape(STATUS_LABELS.get(d_cons_raw, d_cons_raw))
            d_revs = html.escape(", ".join(set([str(r.get('reviewer', '')) for r in d.get('reviews', [])]))) or "None"

            # P2-9: Only add "..." when actually truncated
            truncated = d_measure[:50] + '...' if len(d_measure) > 50 else d_measure

            # P2-2: Use proper badge color mapping
            badge_color = BADGE_COLORS.get(d_cons_raw, DEFAULT_BADGE_COLOR)

            html_content += f"""
                            <tr>
                                <td class="px-4 py-3 whitespace-nowrap font-medium text-gray-800">{truncated}</td>
                                <td class="px-4 py-3 whitespace-nowrap text-gray-600">{d_conf}</td>
                                <td class="px-4 py-3 whitespace-nowrap">
                                    <span class="px-2 py-1 rounded text-xs font-semibold {badge_color}">{d_cons_label}</span>
                                </td>
                                <td class="px-4 py-3 whitespace-nowrap text-gray-500 text-xs">{d_revs}</td>
                            </tr>
            """

        html_content += f"""
                        </tbody>
                    </table>
                </div>

                <h2 class="text-2xl font-bold text-gray-900 mb-4">Identified Discrepancies ({len(discrepancies)})</h2>
                <div class="space-y-6">
        """

        if not discrepancies:
            html_content += """
                <div class="bg-green-50 p-6 rounded-lg text-green-800 border border-green-200">
                    No discrepancies found!
                </div>
            """
        else:
            for idx, d in enumerate(discrepancies):
                d_type = html.escape(str(d.get('type', 'UNKNOWN')))
                reason = html.escape(str(d.get('reason', '')))
                measure = html.escape(str(d.get('publication_outcome') or d.get('protocol_outcome', '')))
                consensus_raw = str(d.get('consensus_status', 'PENDING'))
                consensus = html.escape(consensus_raw)
                consensus_label = html.escape(STATUS_LABELS.get(consensus_raw, consensus_raw))

                # P2-2: Use proper badge color mapping for detail cards too
                consensus_badge = BADGE_COLORS.get(consensus_raw, DEFAULT_BADGE_COLOR)

                html_content += f"""
                <div class="bg-white rounded-lg shadow overflow-hidden border border-gray-200">
                    <div class="p-5 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
                        <div class="flex items-center gap-3">
                            <span class="px-3 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded">{d_type}</span>
                            <h3 class="font-semibold text-gray-800">Outcome: {measure}</h3>
                        </div>
                        <span class="px-3 py-1 rounded text-xs border {consensus_badge}">
                            Consensus: {consensus_label}
                        </span>
                    </div>
                    <div class="p-5">
                        <p class="text-gray-700 mb-4"><strong>Flag Reason:</strong> {reason}</p>
                        <h4 class="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Reviewer Feedback</h4>
                """

                reviews = d.get('reviews', [])
                if not reviews:
                    html_content += '<p class="text-sm text-gray-500 italic">No reviews submitted yet.</p>'
                else:
                    html_content += '<ul class="space-y-3">'
                    for r in reviews:
                        reviewer = html.escape(str(r.get('reviewer', 'Anonymous')))
                        r_status = html.escape(str(r.get('status', '')))
                        comment = html.escape(str(r.get('comment', '')))
                        icon = "&#x2705;" if r_status == "CONFIRMED" else "&#x274C;" if r_status == "FALSE_POSITIVE" else "&#x26A0;"

                        html_content += f"""
                            <li class="bg-gray-50 p-3 rounded border border-gray-100 text-sm">
                                <div class="flex justify-between mb-1">
                                    <span class="font-semibold text-gray-700">{reviewer}</span>
                                    <span>{icon} {r_status}</span>
                                </div>
                                <p class="text-gray-600">"{comment}"</p>
                            </li>
                        """
                    html_content += '</ul>'

                html_content += "</div></div>"

        # P0-8: Add TOOL_DISCLAIMER before closing body
        escaped_disclaimer = html.escape(TOOL_DISCLAIMER)
        html_content += f"""
                </div>

                <!-- P2-10: NCT link with rel attributes already handled above -->

                <div class="mt-10 p-4 rounded bg-gray-100 border border-gray-300 text-gray-600 text-xs">
                    <p><strong>Disclaimer:</strong> {escaped_disclaimer}</p>
                </div>
            </div>
        </body>
        </html>"""

        with open(self.output_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML Dashboard generated successfully at: {self.output_html_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate HTML dashboard from Integrity Report.")
    parser.add_argument("--report", required=True, help="Path to the JSON report.")
    parser.add_argument("--output", required=True, help="Path to save the HTML file.")
    args = parser.parse_args()
    reporter = HTMLReporter(args.report, args.output)
    reporter.generate()


if __name__ == "__main__":
    main()
