// A project-level extension, loaded through a project .pi/settings.json, so it loads
// only when pi trusts the project. The fake model reports `project_probe` in TOOLS.
export default function (pi) {
	pi.registerTool({
		name: "project_probe",
		label: "Project probe",
		description: "Present only when the project is trusted",
		parameters: { type: "object", properties: {} },
		async execute() {
			return { content: [{ type: "text", text: "ok" }], details: undefined };
		},
	});
}
