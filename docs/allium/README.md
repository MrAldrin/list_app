# Allium pilot

Optional spec trial. Run the commands from the repository root.

A [draft sharing behavior spec](public-sharing.allium) is available for
review alongside the [public-sharing guide](../public-sharing.md). It is a
small trial, not a replacement for the guide or pytest tests. The Pi skills are
installed locally under `.pi/skills/` (ignored by the current `.gitignore`);
`skills-lock.json` records their source. To set up another checkout, run
`npx skills add juxt/allium -a pi -s allium distill elicit propagate tend weed witness -y`,
then reload Pi. Install the optional CLI separately with
`cargo install allium-cli --locked`; validate the draft with
`allium check docs/allium/public-sharing.allium`. Review the draft's open
question before treating it as intended behavior. Do not run an autonomous
`/skill:allium` implementation loop without agreeing on the next step.
