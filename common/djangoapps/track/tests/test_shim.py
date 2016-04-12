"""Ensure emitted events contain the fields legacy processors expect to find."""

from collections import namedtuple

import ddt
from mock import sentinel
from django.test.utils import override_settings

from openedx.core.lib.tests.assertions.events import assert_events_equal

from . import EventTrackingTestCase, FROZEN_TIME
from ..shim import EventShimProcessor


LEGACY_SHIM_PROCESSOR = [
    {
        'ENGINE': 'track.shim.LegacyFieldMappingProcessor'
    }
]

GOOGLE_ANALYTICS_PROCESSOR = [
    {
        'ENGINE': 'track.shim.GoogleAnalyticsProcessor'
    }
]


@override_settings(
    EVENT_TRACKING_PROCESSORS=LEGACY_SHIM_PROCESSOR,
)
class LegacyFieldMappingProcessorTestCase(EventTrackingTestCase):
    """Ensure emitted events contain the fields legacy processors expect to find."""

    def test_event_field_mapping(self):
        data = {sentinel.key: sentinel.value}

        context = {
            'accept_language': sentinel.accept_language,
            'referer': sentinel.referer,
            'username': sentinel.username,
            'session': sentinel.session,
            'ip': sentinel.ip,
            'host': sentinel.host,
            'agent': sentinel.agent,
            'path': sentinel.path,
            'user_id': sentinel.user_id,
            'course_id': sentinel.course_id,
            'org_id': sentinel.org_id,
            'client_id': sentinel.client_id,
        }
        with self.tracker.context('test', context):
            self.tracker.emit(sentinel.name, data)

        emitted_event = self.get_event()

        expected_event = {
            'accept_language': sentinel.accept_language,
            'referer': sentinel.referer,
            'event_type': sentinel.name,
            'name': sentinel.name,
            'context': {
                'user_id': sentinel.user_id,
                'course_id': sentinel.course_id,
                'org_id': sentinel.org_id,
                'path': sentinel.path,
            },
            'event': data,
            'username': sentinel.username,
            'event_source': 'server',
            'time': FROZEN_TIME,
            'agent': sentinel.agent,
            'host': sentinel.host,
            'ip': sentinel.ip,
            'page': None,
            'session': sentinel.session,
        }
        assert_events_equal(expected_event, emitted_event)

    def test_missing_fields(self):
        self.tracker.emit(sentinel.name)

        emitted_event = self.get_event()

        expected_event = {
            'accept_language': '',
            'referer': '',
            'event_type': sentinel.name,
            'name': sentinel.name,
            'context': {},
            'event': {},
            'username': '',
            'event_source': 'server',
            'time': FROZEN_TIME,
            'agent': '',
            'host': '',
            'ip': '',
            'page': None,
            'session': '',
        }
        assert_events_equal(expected_event, emitted_event)


@override_settings(
    EVENT_TRACKING_PROCESSORS=GOOGLE_ANALYTICS_PROCESSOR,
)
class GoogleAnalyticsProcessorTestCase(EventTrackingTestCase):
    """Ensure emitted events contain the fields necessary for Google Analytics."""

    def test_event_fields(self):
        """ Test that course_id is added as the label if present, and nonInteraction is set. """
        data = {sentinel.key: sentinel.value}

        context = {
            'path': sentinel.path,
            'user_id': sentinel.user_id,
            'course_id': sentinel.course_id,
            'org_id': sentinel.org_id,
            'client_id': sentinel.client_id,
        }
        with self.tracker.context('test', context):
            self.tracker.emit(sentinel.name, data)

        emitted_event = self.get_event()

        expected_event = {
            'context': context,
            'data': data,
            'label': sentinel.course_id,
            'name': sentinel.name,
            'nonInteraction': 1,
            'timestamp': FROZEN_TIME,
        }
        assert_events_equal(expected_event, emitted_event)

    def test_no_course_id(self):
        """ Test that a label is not added if course_id is not specified, but nonInteraction is still set. """
        data = {sentinel.key: sentinel.value}

        context = {
            'path': sentinel.path,
            'user_id': sentinel.user_id,
            'client_id': sentinel.client_id,
        }
        with self.tracker.context('test', context):
            self.tracker.emit(sentinel.name, data)

        emitted_event = self.get_event()

        expected_event = {
            'context': context,
            'data': data,
            'name': sentinel.name,
            'nonInteraction': 1,
            'timestamp': FROZEN_TIME,
        }
        assert_events_equal(expected_event, emitted_event)


@override_settings(
    EVENT_TRACKING_BACKENDS={
        '0': {
            'ENGINE': 'eventtracking.backends.routing.RoutingBackend',
            'OPTIONS': {
                'backends': {
                    'first': {'ENGINE': 'track.tests.InMemoryBackend'}
                },
                'processors': [
                    {
                        'ENGINE': 'track.shim.GoogleAnalyticsProcessor'
                    }
                ]
            }
        },
        '1': {
            'ENGINE': 'eventtracking.backends.routing.RoutingBackend',
            'OPTIONS': {
                'backends': {
                    'second': {
                        'ENGINE': 'track.tests.InMemoryBackend'
                    }
                }
            }
        }
    }
)
class MultipleShimGoogleAnalyticsProcessorTestCase(EventTrackingTestCase):
    """Ensure changes don't impact other backends"""

    def test_multiple_backends(self):
        data = {
            sentinel.key: sentinel.value,
        }

        context = {
            'path': sentinel.path,
            'user_id': sentinel.user_id,
            'course_id': sentinel.course_id,
            'org_id': sentinel.org_id,
            'client_id': sentinel.client_id,
        }
        with self.tracker.context('test', context):
            self.tracker.emit(sentinel.name, data)

        segment_emitted_event = self.tracker.backends['0'].backends['first'].events[0]
        log_emitted_event = self.tracker.backends['1'].backends['second'].events[0]

        expected_event = {
            'context': context,
            'data': data,
            'label': sentinel.course_id,
            'name': sentinel.name,
            'nonInteraction': 1,
            'timestamp': FROZEN_TIME,
        }
        assert_events_equal(expected_event, segment_emitted_event)

        expected_event = {
            'context': context,
            'data': data,
            'name': sentinel.name,
            'timestamp': FROZEN_TIME,
        }
        assert_events_equal(expected_event, log_emitted_event)


SequenceDDT = namedtuple('SequenceDDT', ['action', 'tab_count', 'current_tab', 'legacy_event_type'])


@ddt.ddt
class EventShimProcessorTestCase(EventTrackingTestCase):
    """
    Test EventShimProcessor
    """

    @ddt.data(
        SequenceDDT(action='next', tab_count=5, current_tab=3, legacy_event_type='seq_next'),
        SequenceDDT(action='next', tab_count=5, current_tab=5, legacy_event_type=None),
        SequenceDDT(action='previous', tab_count=5, current_tab=3, legacy_event_type='seq_prev'),
        SequenceDDT(action='previous', tab_count=5, current_tab=1, legacy_event_type=None),
    )
    def test_sequence_linear_navigation(self, sequence_ddt):
        event_name = 'edx.ui.lms.sequence.{}_selected'.format(sequence_ddt.action)

        event = {
            'name': event_name,
            'event': {
                'current_tab': sequence_ddt.current_tab,
                'tab_count': sequence_ddt.tab_count,
                'id': 'ABCDEFG',
            }
        }

        process_event_shim = EventShimProcessor()
        result = process_event_shim(event)
        # Original event is not modified
        self.assertIsNot(result, event)
        #self.assertNotIn('old', event['event'])
        #self.assertNotIn('new', event['event'])

        self.assertEqual(result['name'], event['name'])

        # Legacy fields get added when needed
        if sequence_ddt.action == 'next':
            offset = 1
        else:
            offset = -1
        if sequence_ddt.legacy_event_type:
            self.assertEqual(result['event_type'], sequence_ddt.legacy_event_type)
            self.assertEqual(result['event']['old'], sequence_ddt.current_tab)
            self.assertEqual(result['event']['new'], sequence_ddt.current_tab + offset)
        else:
            self.assertNotIn('event_type', result)
            self.assertNotIn('old', result['event'])
            self.assertNotIn('new', result['event'])
