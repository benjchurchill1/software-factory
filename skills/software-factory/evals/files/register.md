# Requirements register: clinic booking v1

| ID | Requirement | Pass criterion | Verify method |
| --- | --- | --- | --- |
| BK-CORE-001 | Staff can create an appointment | POST /api/appointments with a valid body returns 201 and the row exists | integration test |
| BK-CORE-002 | The booking screen is fast and intuitive | Users find it easy to use | review |
| BK-CORE-003 | A patient can cancel an appointment | Cancelling sets status CANCELLED and frees the slot | integration test |
| BK-CORE-004 | Reminders are sent the day before | An SMS is delivered to the patient's phone 24 h before | e2e against the live SMS provider |
| BK-CORE-005 | The calendar shows the week's appointments | GET /api/appointments?week= returns the week's rows | integration test |
| BK-CORE-006 | Reports export to CSV | An export endpoint returns CSV | integration test |

## Definition of done

Every row is PASS, and the product is ready for customers.
