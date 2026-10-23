# Development and publication policy

Original development, work in progress and detailed research are maintained in
the owner's private workbench. This public repository is the selected publication
of original mod source, generators, regression tests and useful public documentation.
It is not an automatic mirror of the private development history.

Publish here only when the owner explicitly asks for that public update. A request
to implement or test a mod, save knowledge, commit source, or update the private
workbench does not authorize a public push. An authorization for one publication
does not carry forward to later tasks. Never change repository visibility implicitly.

For an authorized export, start from a clean checkout of the current public main.
Compare completed source changes with the public tree and select the required code,
tests, provenance and public instructions. Keep experimental status and remaining
limits explicit; publishing source does not establish a new release or gameplay
acceptance. Do not bump versions or rebuild frozen payloads merely for synchronization.

Do not merge the private branch or mirror all its commits into this repository.
Do not export raw personal journals, local path maps, private settings, saves,
captures, diagnostic residue, binary game inputs, backups or transfer archives.
Unfinished local experiments remain in the private workbench unless the owner
specifically requests their publication and they have a clean, documented source boundary.

Before pushing, inspect the exact staged blobs with `python -B -m infra.public_tree --tracked`, review the diff and run checks appropriate to the selected changes.
An unchanged runtime does not need new gameplay certification for a documentation
update. Record exported commits and verification in the private development log;
keep that log and its private evidence out of this public tree.
