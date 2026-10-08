import 'package:flutter_test/flutter_test.dart';
import 'package:hospital_mobile/core/models.dart';

void main() {
  group('SessionUser', () {
    test('identifies portal accounts as patients', () {
      const patient = SessionUser(id: 1, username: 'p', role: 'Patient');
      const nurse = SessionUser(id: 2, username: 'n', role: 'Nurse');
      expect(patient.isPatient, isTrue);
      expect(nurse.isPatient, isFalse);
    });

    test('only ward roles get the bed board', () {
      for (final role in ['Nurse', 'Doctor', 'Admin']) {
        expect(SessionUser(id: 1, username: 'x', role: role).isWardStaff, isTrue,
            reason: '$role works on the ward');
      }
      for (final role in ['Patient', 'Pharmacy', 'Laboratory', 'Billing', 'Insurance']) {
        expect(SessionUser(id: 1, username: 'x', role: role).isWardStaff, isFalse,
            reason: '$role has no ward duties');
      }
    });

    test('parses the backend payload including the linked patient', () {
      final user = SessionUser.fromJson({
        'id': 7,
        'username': 'ramesh',
        'role': 'Patient',
        'patient_id': 42,
        'full_name': 'Ramesh Kumar',
      });
      expect(user.id, 7);
      expect(user.patientId, 42);
      expect(user.fullName, 'Ramesh Kumar');
    });
  });

  group('Appointment', () {
    test('only open appointments can be cancelled', () {
      Appointment make(String status) => Appointment(
            id: 1,
            appointmentDate: '2026-10-01T09:00:00',
            status: status,
          );
      expect(make('Booked').isActive, isTrue);
      expect(make('Waiting').isActive, isTrue);
      expect(make('Cancelled').isActive, isFalse);
      expect(make('Completed').isActive, isFalse);
    });
  });

  group('PrescribedMedicine', () {
    test('renders a readable dosing schedule', () {
      const both = PrescribedMedicine(name: 'Tab A', morning: true, night: true);
      expect(both.timing, 'Morning, Night');
      const none = PrescribedMedicine(name: 'Tab B');
      expect(none.timing, '—');
    });

    test('reads the timing flags from the API shape', () {
      final medicine = PrescribedMedicine.fromJson({
        'name': 'Tab. Metformin',
        'quantity': 10,
        'timing_morning': true,
        'timing_afternoon': false,
        'timing_night': true,
        'duration': '5 days',
      });
      expect(medicine.name, 'Tab. Metformin');
      expect(medicine.quantity, 10);
      expect(medicine.timing, 'Morning, Night');
      expect(medicine.duration, '5 days');
    });
  });

  group('LabResultRow', () {
    test('flags anything outside the reference range', () {
      expect(const LabResultRow(parameter: 'Hb', flag: 'Normal').isAbnormal, isFalse);
      expect(const LabResultRow(parameter: 'Hb', flag: 'High').isAbnormal, isTrue);
      expect(const LabResultRow(parameter: 'Hb').isAbnormal, isFalse);
    });
  });

  group('BedTile', () {
    test('derives occupancy from the status string', () {
      final occupied = BedTile.fromJson({
        'bed_id': 1, 'bed_code': 'B1', 'status': 'Occupied',
        'daily_charge': 2500, 'patient_name': 'Asha',
      });
      expect(occupied.isOccupied, isTrue);
      expect(occupied.isAvailable, isFalse);
      expect(occupied.patientName, 'Asha');
      expect(occupied.dailyCharge, 2500);

      final free = BedTile.fromJson({
        'bed_id': 2, 'bed_code': 'B2', 'status': 'Available', 'daily_charge': 0,
      });
      expect(free.isAvailable, isTrue);
      expect(free.patientName, isNull);
    });
  });

  group('AdmissionDetail', () {
    test('pulls the patient and bed out of the nested payload', () {
      final detail = AdmissionDetail.fromJson({
        'id': 5,
        'patient_id': 9,
        'patient': {'name': 'Asha', 'age': 44, 'gender': 'Female'},
        'bed': {'bed_code': 'B12'},
        'ward_number': 'ICU',
        'room_number': '101',
        'admission_date': '2026-10-01T08:00:00',
        'status': 'Admitted',
        'admission_type': 'Emergency',
        'length_of_stay_days': 3,
        'billable_room_charge': 7500,
        'nursing_notes': [
          {'id': 1, 'recorded_at': '2026-10-01T09:00:00', 'shift': 'Morning',
           'bp_systolic': 120, 'bp_diastolic': 80, 'is_critical': false},
        ],
        'medication_orders': [
          {'id': 3, 'medicine_name': 'Inj. X', 'status': 'Active'},
        ],
      });
      expect(detail.patientName, 'Asha');
      expect(detail.bedCode, 'B12');
      expect(detail.isAdmitted, isTrue);
      expect(detail.lengthOfStayDays, 3);
      expect(detail.nursingNotes.single.bp, '120/80');
      expect(detail.medicationOrders.single.medicineName, 'Inj. X');
      expect(detail.medicationOrders.single.isActive, isTrue);
    });

    test('tolerates an admission with no bed and no notes', () {
      final detail = AdmissionDetail.fromJson({
        'id': 6,
        'patient_id': 10,
        'admission_date': '2026-10-02T08:00:00',
        'status': 'Admitted',
      });
      expect(detail.bedCode, isNull);
      expect(detail.nursingNotes, isEmpty);
      expect(detail.medicationOrders, isEmpty);
      expect(detail.patientName, isNull);
      // A discharged admission must not be treated as active.
      expect(detail.isAdmitted, isTrue);
    });
  });

  group('NursingNote', () {
    test('formats a partial blood pressure without inventing a value', () {
      final note = NursingNote.fromJson({
        'id': 1, 'recorded_at': '2026-10-01T09:00:00', 'shift': 'Night',
        'bp_systolic': 130, 'is_critical': true,
      });
      expect(note.bp, '—'); // diastolic missing, so no reading is shown
      expect(note.isCritical, isTrue);
      expect(note.shift, 'Night');
    });
  });
}
