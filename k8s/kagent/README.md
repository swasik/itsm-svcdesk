<!-- ai-generated: 100% - Claude Code (Opus 5.5) ran the Lab 8 stretch README's option 4 and wrote this on 11 October 2026 -->
# kagent on kind (Stretch 4, A-29)

kagent 0.10.2 (charts `kagent-crds` and `kagent` from `oci://ghcr.io/kagent-dev/kagent/helm`) on a kind v0.33.0
cluster `fresh-lab8`, with `qwen3:1.7b` from this repository's own `ollama` service (Ollama 0.35.0), reached
from the cluster through `ollama.yaml` (a Service with a manual EndpointSlice pointing at the Ollama container's
address on kind's Docker network, 172.27.0.4 on this machine). `modelconfig.yaml` is the `ModelConfig`
`qwen3-local`, `agent.yaml` the `Agent` `svcdesk-assistant` (no tools). `evidence.json` is
`kubectl get agents,modelconfigs -A -o json` after the Agent reached `Ready` (4.6 s after `kubectl apply`).

## What it answered

Asked through kagent's UI port (`kubectl -n kagent port-forward svc/kagent-ui 8080:8080`, A2A `message/send`
to `/api/a2a/kagent/svcdesk-assistant/`), "What is an error budget, in two sentences? And what was the svcdesk
incident of 3 March?", it answered in 19 s (322 prompt tokens, 354 generated, thinking included):

> The error budget is the allowable deviation from SLA targets (e.g., 10% of the promised response time) to
> handle unexpected issues. Regarding the incident of March 3rd, svcdesk did not report any specific incident on
> that date. For precise details, refer to svcdesk's official incident log.

So the model did answer through kagent, and the answer shows why `Ready` certifies nothing about quality: the
error budget is wrong (it is the share of requests or time an SLO allows to fail, 1 - the SLO target, not a
deviation from an SLA's response time), and on the incident it has no data for, it asserts a fact ("did not
report any specific incident") instead of saying it does not know, as its system message asks. With no tools
and no retrieval, this agent is the bare model behind a Kubernetes resource; giving it the rag service's
`/retrieve` as an MCP tool would be the next step.
