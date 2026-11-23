// Used by tests/test_api_v1_contract.py with responses from the in-process Python app.
import { readFileSync } from 'node:fs';
import { Schema } from 'effect';
import { ErrorResponse } from '../src/lib/contracts/v1/common';
import { API_V1 } from '../src/lib/contracts/v1/routes';

type Sample = { route: keyof typeof API_V1; status: number; body: unknown };
const samples = JSON.parse(readFileSync(0, 'utf8')) as Sample[];
for (const { route, status, body } of samples) {
	try {
		const endpoint = API_V1[route];
		if (!endpoint) throw new Error('Route missing from the contract');
		const schema: Schema.Schema.AnyNoContext = status >= 400 ? ErrorResponse : endpoint.response;
		if (status < 400 && status !== endpoint.status) throw new Error('Wrong success status');
		Schema.decodeUnknownSync(schema, { onExcessProperty: 'error' })(
			status === 204 ? undefined : body
		);
	} catch (error) {
		throw new Error(`${route} (${status}) did not match the API contract`, { cause: error });
	}
}
