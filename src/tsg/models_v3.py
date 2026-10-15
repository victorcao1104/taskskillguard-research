"""Strict, evidence-preserving Responses protocol on the existing shared budget.

No automatic retries, alternate ledgers, key discovery, or tool access. A failed
request remains cached, and unknown billing retains its original reservation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import urllib.error
import urllib.request

from jsonschema import Draft202012Validator

from .models import Client, make_request, utcnow


class DuplicateJSONKey(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKey(key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError('NONFINITE_JSON_NUMBER: ' + value)


def validate_record(raw, response_schema=None):
    """Validate live or historical raw evidence, never concatenate or salvage.

    Historical records with only completed status/text are supported. When a
    response envelope exists it is the authoritative extraction source; legacy
    concatenated ``text`` is never trusted over it.
    """
    result = {'protocol_valid':False, 'diagnostic_codes':[], 'text':'',
              'prediction':None, 'schema_errors':[]}
    codes = result['diagnostic_codes']
    if not isinstance(raw, dict):
        codes.append('MALFORMED_RECORD')
        return result
    status = raw.get('status')
    if status is not None and not isinstance(status, str):
        codes.append('MALFORMED_RESPONSE_STATUS')
        return result
    if status in {'api_error','failed'}:
        codes.append('API_ERROR')
        return result
    if status == 'transport_error':
        codes.append('TRANSPORT_ERROR')
        return result
    if status == 'invalid_response':
        codes.append('MALFORMED_RESPONSE')
        return result
    texts = []
    if 'response' in raw:
        response = raw['response']
        if not isinstance(response, dict) or not isinstance(response.get('output'), list):
            codes.append('MALFORMED_RESPONSE')
            return result
        status = response.get('status', status)
        if status is not None and not isinstance(status, str):
            codes.append('MALFORMED_RESPONSE_STATUS')
            return result
        if raw.get('status') is not None and raw['status'] != status:
            codes.append('RESPONSE_STATUS_MISMATCH')
        if response.get('error') is not None or status == 'failed':
            codes.append('API_ERROR')
        if response.get('incomplete_details') is not None:
            codes.append('RESPONSE_INCOMPLETE')
        for item in response['output']:
            if not isinstance(item, dict):
                codes.append('MALFORMED_RESPONSE')
                continue
            if item.get('type') == 'reasoning':
                continue
            if item.get('type') != 'message' or item.get('role') != 'assistant':
                codes.append('UNEXPECTED_OUTPUT_ITEM')
                continue
            if item.get('status') == 'incomplete':
                codes.append('RESPONSE_INCOMPLETE')
            elif item.get('status') not in (None, 'completed'):
                codes.append('RESPONSE_NOT_COMPLETED')
            content = item.get('content')
            if not isinstance(content, list):
                codes.append('MALFORMED_RESPONSE')
                continue
            for part in content:
                if not isinstance(part, dict):
                    codes.append('MALFORMED_RESPONSE')
                elif part.get('type') == 'refusal':
                    codes.append('REFUSAL')
                elif part.get('type') == 'output_text':
                    texts.append(part.get('text'))
                else:
                    codes.append('UNEXPECTED_CONTENT_TYPE')
    elif isinstance(raw.get('text'), str):
        texts = [raw['text']]
    else:
        codes.append('MISSING_OUTPUT_TEXT')
    if status == 'incomplete' or raw.get('status') == 'incomplete':
        codes.append('RESPONSE_INCOMPLETE')
    elif status != 'completed':
        codes.append('RESPONSE_STATUS_UNKNOWN' if status in {None,'unknown'} else 'RESPONSE_NOT_COMPLETED')
    if len(texts) > 1:
        codes.append('MULTIPLE_OUTPUT_TEXT')
    elif not texts or texts == ['']:
        codes.append('MISSING_OUTPUT_TEXT')
    elif not isinstance(texts[0], str):
        codes.append('MALFORMED_OUTPUT_TEXT')
    result['diagnostic_codes'] = list(dict.fromkeys(codes))
    if result['diagnostic_codes']:
        return result
    text = texts[0]
    try:
        obj = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except DuplicateJSONKey:
        result['diagnostic_codes'].append('DUPLICATE_JSON_KEY')
        return result
    except (ValueError, TypeError, RecursionError):
        result['diagnostic_codes'].append('INVALID_JSON')
        return result
    result['prediction'] = obj
    # JSON-object mode is used for all v3 clients, including schema controls.
    if not isinstance(obj, dict):
        result['diagnostic_codes'].append('SCHEMA_VALIDATION_ERROR')
        return result
    if response_schema is not None:
        validator = Draft202012Validator(response_schema)
        errors = sorted(validator.iter_errors(obj), key=lambda e: str(list(e.path)))
        if errors:
            result['diagnostic_codes'].append('SCHEMA_VALIDATION_ERROR')
            result['schema_errors'] = [{'path':list(e.path), 'validator':e.validator,
                                        'message':e.message} for e in errors]
            return result
    result.update(protocol_valid=True, text=text)
    return result


class ClientV3(Client):
    """Client-compatible protocol; only the parent process supplies the budget."""

    def call(self, model, system, prompt, *, tag, max_output=2500, replicate=0,
             response_schema=None):
        request = make_request(model, system, prompt, max_output)
        if response_schema is not None:
            Draft202012Validator.check_schema(response_schema)
            request['text']['format'] = {'type':'json_schema', 'name':'tsg_response_v3',
                                         'strict':True, 'schema':copy.deepcopy(response_schema)}
        fingerprint = hashlib.sha256(json.dumps(
            {'request':request,'replicate':replicate}, sort_keys=True,
            ensure_ascii=False).encode()).hexdigest()
        with self.request_locks_guard:
            lock = self.request_locks.setdefault(fingerprint, threading.Lock())
        with lock:
            return self._call_locked_v3(model, request, fingerprint, tag, max_output,
                                        replicate, response_schema)

    def _call_locked_v3(self, model, request, fingerprint, tag, max_output,
                        replicate, response_schema):
        path = self.out / (fingerprint + '.json')
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            return {**record, **validate_record(record, response_schema)}
        # Exactly the existing reservation rule, including full schema bytes.
        rid = self.budget.reserve(model,
            len(json.dumps(request, ensure_ascii=False).encode()) + 4096, max_output)
        started = time.perf_counter()
        record = {'tag':tag, 'request_hash':fingerprint, 'replicate':replicate,
                  'request':request, 'timestamp_utc':utcnow(), 'reservation_id':rid}
        req = urllib.request.Request('https://api.openai.com/v1/responses',
            data=json.dumps(request).encode(),
            headers={'Authorization':'Bearer ' + self.key,'Content-Type':'application/json'},
            method='POST')
        try:
            with urllib.request.urlopen(req, timeout=120) as stream:
                response = json.load(stream)
            usage = response.get('usage', {}) if isinstance(response, dict) else {}
            self.budget.settle(rid, usage)
            record.update(status=response.get('status','unknown') if isinstance(response, dict)
                          else 'invalid_response', response=response, usage=usage)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read()).get('error', {})
                if not isinstance(error, dict):
                    error = {}
            except (ValueError, TypeError, AttributeError):
                error = {}
            record.update(status='api_error', http_status=exc.code,
                          error_code=error.get('code'), error_type=error.get('type'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            record.update(status='invalid_response', error_type='INVALID_API_JSON')
        except Exception as exc:
            record.update(status='transport_error', error_type=type(exc).__name__)
        record.update(validate_record(record, response_schema))
        record['elapsed_seconds'] = time.perf_counter() - started
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        return record
