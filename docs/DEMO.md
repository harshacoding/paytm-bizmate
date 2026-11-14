# Scaffold smoke check

This is a developer smoke check, not the final three-minute PRD demo.

1. Run `npm run dev` from the repository root.
2. Open `http://127.0.0.1:5173`. Confirm the local/synthetic/memory labels and loaded merchant.
3. Choose a sample request and select **Start a task**. A new task appears with an awaiting-input state and a clear implementation-pending message.
4. Open the settlement preview and its source references. These are fixture references, not evidence from the task.
5. Edit the sample offer. The send button remains disabled and does not send anything.
6. Stop the backend to check the connection error and retry state. Restart; new tasks are gone because memory storage is temporary.
7. Run `npm run check` for the automated checks.

BM-18 will replace this smoke check with the final demo after BM-03 to BM-17 deliver durable execution, approvals, fresh-credit resolution, independent campaign status and human handoff. The complete PRD specifies the final scenario and ground truth.
