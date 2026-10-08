/// Domain models mirrored from the backend Pydantic schemas.
///
/// Every model exposes `fromJson` and only the fields the mobile client actually
/// renders, so a backend addition never breaks the app.
library;

class SessionUser {
  final int id;
  final String username;
  final String role;
  final int? patientId;
  final String? fullName;

  const SessionUser({
    required this.id,
    required this.username,
    required this.role,
    this.patientId,
    this.fullName,
  });

  bool get isPatient => role == 'Patient';

  /// Roles that work on the ward and therefore get the bed board.
  bool get isWardStaff =>
      role == 'Nurse' || role == 'Doctor' || role == 'Admin';

  factory SessionUser.fromJson(Map<String, dynamic> json) => SessionUser(
        id: json['id'] as int,
        username: json['username'] as String,
        role: json['role'] as String,
        patientId: json['patient_id'] as int?,
        fullName: json['full_name'] as String?,
      );
}

class AuthTokens {
  final String accessToken;
  final String? refreshToken;
  final String role;

  const AuthTokens({required this.accessToken, this.refreshToken, required this.role});

  factory AuthTokens.fromJson(Map<String, dynamic> json) => AuthTokens(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String?,
        role: (json['role'] ?? '') as String,
      );
}

class PatientProfile {
  final int id;
  final String name;
  final int age;
  final String gender;
  final String? phone;
  final String? email;
  final String? address;
  final String? bloodGroup;
  final String? aadhaarMasked;

  const PatientProfile({
    required this.id,
    required this.name,
    required this.age,
    required this.gender,
    this.phone,
    this.email,
    this.address,
    this.bloodGroup,
    this.aadhaarMasked,
  });

  factory PatientProfile.fromJson(Map<String, dynamic> json) => PatientProfile(
        id: json['id'] as int,
        name: json['name'] as String,
        age: json['age'] as int,
        gender: json['gender'] as String,
        phone: json['phone'] as String?,
        email: json['email'] as String?,
        address: json['address'] as String?,
        bloodGroup: json['blood_group'] as String?,
        aadhaarMasked: json['aadhaar_masked'] as String?,
      );
}

class Appointment {
  final int id;
  final String appointmentDate;
  final String? timeSlot;
  final String? doctorName;
  final String? reason;
  final String status;

  const Appointment({
    required this.id,
    required this.appointmentDate,
    this.timeSlot,
    this.doctorName,
    this.reason,
    required this.status,
  });

  bool get isActive => status != 'Cancelled' && status != 'Completed';

  factory Appointment.fromJson(Map<String, dynamic> json) => Appointment(
        id: json['id'] as int,
        appointmentDate: json['appointment_date'] as String,
        timeSlot: json['time_slot'] as String?,
        doctorName: json['doctor_name'] as String?,
        reason: json['reason'] as String?,
        status: json['status'] as String,
      );
}

class PrescribedMedicine {
  final String name;
  final int? quantity;
  final String? duration;
  final String? instructions;
  final bool morning;
  final bool afternoon;
  final bool night;
  final String? relation;

  const PrescribedMedicine({
    required this.name,
    this.quantity,
    this.duration,
    this.instructions,
    this.morning = false,
    this.afternoon = false,
    this.night = false,
    this.relation,
  });

  String get timing {
    final parts = <String>[
      if (morning) 'Morning',
      if (afternoon) 'Afternoon',
      if (night) 'Night',
    ];
    return parts.isEmpty ? '—' : parts.join(', ');
  }

  factory PrescribedMedicine.fromJson(Map<String, dynamic> json) => PrescribedMedicine(
        name: (json['name'] ?? '') as String,
        quantity: json['quantity'] as int?,
        duration: json['duration'] as String?,
        instructions: json['instructions'] as String?,
        morning: json['timing_morning'] == true,
        afternoon: json['timing_afternoon'] == true,
        night: json['timing_night'] == true,
        relation: json['timing_relation'] as String?,
      );
}

class Prescription {
  final int id;
  final String date;
  final String? doctorName;
  final String? diagnosis;
  final String? advice;
  final List<PrescribedMedicine> medicines;

  const Prescription({
    required this.id,
    required this.date,
    this.doctorName,
    this.diagnosis,
    this.advice,
    required this.medicines,
  });

  factory Prescription.fromJson(Map<String, dynamic> json) => Prescription(
        id: json['id'] as int,
        date: json['date'] as String,
        doctorName: json['doctor_name'] as String?,
        diagnosis: json['diagnosis'] as String?,
        advice: json['advice'] as String?,
        medicines: ((json['medicines'] ?? []) as List)
            .map((m) => PrescribedMedicine.fromJson(m as Map<String, dynamic>))
            .toList(),
      );
}

class LabResultRow {
  final String parameter;
  final String? result;
  final String? unit;
  final String? range;
  final String? flag;

  const LabResultRow({
    required this.parameter,
    this.result,
    this.unit,
    this.range,
    this.flag,
  });

  bool get isAbnormal => flag != null && flag != 'Normal';

  factory LabResultRow.fromJson(Map<String, dynamic> json) => LabResultRow(
        parameter: (json['parameter'] ?? '') as String,
        result: json['result']?.toString(),
        unit: json['unit'] as String?,
        range: json['range'] as String?,
        flag: json['flag'] as String?,
      );
}

class LabReport {
  final int id;
  final String testName;
  final String dateConducted;
  final String status;
  final bool isAbnormal;
  final String? verifiedBy;
  final String? interpretation;
  final List<LabResultRow> results;

  const LabReport({
    required this.id,
    required this.testName,
    required this.dateConducted,
    required this.status,
    required this.isAbnormal,
    this.verifiedBy,
    this.interpretation,
    required this.results,
  });

  factory LabReport.fromJson(Map<String, dynamic> json) => LabReport(
        id: json['id'] as int,
        testName: json['test_name'] as String,
        dateConducted: json['date_conducted'] as String,
        status: (json['status'] ?? 'Final') as String,
        isAbnormal: json['is_abnormal'] == true,
        verifiedBy: json['verified_by'] as String?,
        interpretation: json['interpretation'] as String?,
        results: ((json['results'] ?? []) as List)
            .map((r) => LabResultRow.fromJson(r as Map<String, dynamic>))
            .toList(),
      );
}

class LabOrderProgress {
  final int id;
  final String testName;
  final String orderDate;
  final String status;
  final String priority;
  final bool reportReady;

  const LabOrderProgress({
    required this.id,
    required this.testName,
    required this.orderDate,
    required this.status,
    required this.priority,
    required this.reportReady,
  });

  factory LabOrderProgress.fromJson(Map<String, dynamic> json) => LabOrderProgress(
        id: json['id'] as int,
        testName: json['test_name'] as String,
        orderDate: json['order_date'] as String,
        status: json['status'] as String,
        priority: (json['priority'] ?? 'Routine') as String,
        reportReady: json['report_ready'] == true,
      );
}

class BillItem {
  final String name;
  final num amount;
  const BillItem({required this.name, required this.amount});

  factory BillItem.fromJson(Map<String, dynamic> json) => BillItem(
        name: (json['name'] ?? '') as String,
        amount: (json['amount'] ?? 0) as num,
      );
}

class PortalBill {
  final int id;
  final String billType;
  final String billDate;
  final String description;
  final double total;
  final String? status;
  final List<BillItem> items;

  const PortalBill({
    required this.id,
    required this.billType,
    required this.billDate,
    required this.description,
    required this.total,
    this.status,
    required this.items,
  });

  factory PortalBill.fromJson(Map<String, dynamic> json) => PortalBill(
        id: json['id'] as int,
        billType: json['bill_type'] as String,
        billDate: json['bill_date'] as String,
        description: (json['description'] ?? '') as String,
        total: ((json['total'] ?? 0) as num).toDouble(),
        status: json['status'] as String?,
        items: ((json['items'] ?? []) as List)
            .map((i) => BillItem.fromJson(i as Map<String, dynamic>))
            .toList(),
      );
}

class PortalDocument {
  final String type;
  final int id;
  final String title;
  final String? date;
  final String? subtitle;

  const PortalDocument({
    required this.type,
    required this.id,
    required this.title,
    this.date,
    this.subtitle,
  });

  factory PortalDocument.fromJson(Map<String, dynamic> json) => PortalDocument(
        type: json['type'] as String,
        id: json['id'] as int,
        title: json['title'] as String,
        date: json['date'] as String?,
        subtitle: json['subtitle'] as String?,
      );
}

class PortalDashboard {
  final PatientProfile profile;
  final Appointment? nextAppointment;
  final int upcomingAppointments;
  final int pendingLabTests;
  final int readyReports;
  final int abnormalReports;
  final int prescriptions;
  final double totalBilled;
  final List<LabOrderProgress> recentLabOrders;

  const PortalDashboard({
    required this.profile,
    this.nextAppointment,
    required this.upcomingAppointments,
    required this.pendingLabTests,
    required this.readyReports,
    required this.abnormalReports,
    required this.prescriptions,
    required this.totalBilled,
    required this.recentLabOrders,
  });

  factory PortalDashboard.fromJson(Map<String, dynamic> json) => PortalDashboard(
        profile: PatientProfile.fromJson(json['profile'] as Map<String, dynamic>),
        nextAppointment: json['next_appointment'] == null
            ? null
            : Appointment.fromJson(json['next_appointment'] as Map<String, dynamic>),
        upcomingAppointments: (json['upcoming_appointments'] ?? 0) as int,
        pendingLabTests: (json['pending_lab_tests'] ?? 0) as int,
        readyReports: (json['ready_reports'] ?? 0) as int,
        abnormalReports: (json['abnormal_reports'] ?? 0) as int,
        prescriptions: (json['prescriptions'] ?? 0) as int,
        totalBilled: ((json['total_billed'] ?? 0) as num).toDouble(),
        recentLabOrders: ((json['recent_lab_orders'] ?? []) as List)
            .map((o) => LabOrderProgress.fromJson(o as Map<String, dynamic>))
            .toList(),
      );
}

// ---------------------------------------------------------------------------
// Ward (IPD)
// ---------------------------------------------------------------------------

class BedTile {
  final int bedId;
  final String bedCode;
  final String status;
  final String? wardName;
  final String? wardType;
  final String? roomNumber;
  final double dailyCharge;
  final int? admissionId;
  final int? patientId;
  final String? patientName;
  final String? attendingDoctor;

  const BedTile({
    required this.bedId,
    required this.bedCode,
    required this.status,
    this.wardName,
    this.wardType,
    this.roomNumber,
    required this.dailyCharge,
    this.admissionId,
    this.patientId,
    this.patientName,
    this.attendingDoctor,
  });

  bool get isOccupied => status == 'Occupied';
  bool get isAvailable => status == 'Available';

  factory BedTile.fromJson(Map<String, dynamic> json) => BedTile(
        bedId: json['bed_id'] as int,
        bedCode: json['bed_code'] as String,
        status: json['status'] as String,
        wardName: json['ward_name'] as String?,
        wardType: json['ward_type'] as String?,
        roomNumber: json['room_number'] as String?,
        dailyCharge: ((json['daily_charge'] ?? 0) as num).toDouble(),
        admissionId: json['admission_id'] as int?,
        patientId: json['patient_id'] as int?,
        patientName: json['patient_name'] as String?,
        attendingDoctor: json['attending_doctor'] as String?,
      );
}

class NursingNote {
  final int id;
  final String recordedAt;
  final String shift;
  final double? temperature;
  final int? pulse;
  final int? bpSystolic;
  final int? bpDiastolic;
  final int? spo2;
  final bool isCritical;
  final String? recordedBy;

  const NursingNote({
    required this.id,
    required this.recordedAt,
    required this.shift,
    this.temperature,
    this.pulse,
    this.bpSystolic,
    this.bpDiastolic,
    this.spo2,
    required this.isCritical,
    this.recordedBy,
  });

  String get bp =>
      (bpSystolic != null && bpDiastolic != null) ? '$bpSystolic/$bpDiastolic' : '—';

  factory NursingNote.fromJson(Map<String, dynamic> json) => NursingNote(
        id: json['id'] as int,
        recordedAt: json['recorded_at'] as String,
        shift: (json['shift'] ?? 'Morning') as String,
        temperature: (json['temperature'] as num?)?.toDouble(),
        pulse: json['pulse'] as int?,
        bpSystolic: json['bp_systolic'] as int?,
        bpDiastolic: json['bp_diastolic'] as int?,
        spo2: json['spo2'] as int?,
        isCritical: json['is_critical'] == true,
        recordedBy: json['recorded_by'] as String?,
      );
}

class MedicationOrder {
  final int id;
  final String medicineName;
  final String? dose;
  final String? route;
  final String? frequency;
  final String status;

  const MedicationOrder({
    required this.id,
    required this.medicineName,
    this.dose,
    this.route,
    this.frequency,
    required this.status,
  });

  bool get isActive => status == 'Active';

  factory MedicationOrder.fromJson(Map<String, dynamic> json) => MedicationOrder(
        id: json['id'] as int,
        medicineName: json['medicine_name'] as String,
        dose: json['dose'] as String?,
        route: json['route'] as String?,
        frequency: json['frequency'] as String?,
        status: (json['status'] ?? 'Active') as String,
      );
}

class AdmissionDetail {
  final int id;
  final int patientId;
  final String? patientName;
  final int? patientAge;
  final String? patientGender;
  final String? bedCode;
  final String? wardNumber;
  final String? roomNumber;
  final String admissionDate;
  final String status;
  final String admissionType;
  final String? reasonForAdmission;
  final int lengthOfStayDays;
  final double billableRoomCharge;
  final List<NursingNote> nursingNotes;
  final List<MedicationOrder> medicationOrders;

  const AdmissionDetail({
    required this.id,
    required this.patientId,
    this.patientName,
    this.patientAge,
    this.patientGender,
    this.bedCode,
    this.wardNumber,
    this.roomNumber,
    required this.admissionDate,
    required this.status,
    required this.admissionType,
    this.reasonForAdmission,
    required this.lengthOfStayDays,
    required this.billableRoomCharge,
    required this.nursingNotes,
    required this.medicationOrders,
  });

  bool get isAdmitted => status == 'Admitted';

  factory AdmissionDetail.fromJson(Map<String, dynamic> json) {
    final patient = json['patient'] as Map<String, dynamic>?;
    final bed = json['bed'] as Map<String, dynamic>?;
    return AdmissionDetail(
      id: json['id'] as int,
      patientId: json['patient_id'] as int,
      patientName: patient?['name'] as String?,
      patientAge: patient?['age'] as int?,
      patientGender: patient?['gender'] as String?,
      bedCode: bed?['bed_code'] as String?,
      wardNumber: json['ward_number'] as String?,
      roomNumber: json['room_number'] as String?,
      admissionDate: json['admission_date'] as String,
      status: json['status'] as String,
      admissionType: (json['admission_type'] ?? 'Planned') as String,
      reasonForAdmission: json['reason_for_admission'] as String?,
      lengthOfStayDays: (json['length_of_stay_days'] ?? 0) as int,
      billableRoomCharge: ((json['billable_room_charge'] ?? 0) as num).toDouble(),
      nursingNotes: ((json['nursing_notes'] ?? []) as List)
          .map((n) => NursingNote.fromJson(n as Map<String, dynamic>))
          .toList(),
      medicationOrders: ((json['medication_orders'] ?? []) as List)
          .map((m) => MedicationOrder.fromJson(m as Map<String, dynamic>))
          .toList(),
    );
  }
}

class IpdStats {
  final int totalBeds;
  final int availableBeds;
  final int occupiedBeds;
  final double occupancyPercent;
  final int currentAdmissions;
  final int admissionsToday;
  final int dischargesToday;
  final int criticalPatients;

  const IpdStats({
    required this.totalBeds,
    required this.availableBeds,
    required this.occupiedBeds,
    required this.occupancyPercent,
    required this.currentAdmissions,
    required this.admissionsToday,
    required this.dischargesToday,
    required this.criticalPatients,
  });

  factory IpdStats.fromJson(Map<String, dynamic> json) => IpdStats(
        totalBeds: (json['total_beds'] ?? 0) as int,
        availableBeds: (json['available_beds'] ?? 0) as int,
        occupiedBeds: (json['occupied_beds'] ?? 0) as int,
        occupancyPercent: ((json['occupancy_percent'] ?? 0) as num).toDouble(),
        currentAdmissions: (json['current_admissions'] ?? 0) as int,
        admissionsToday: (json['admissions_today'] ?? 0) as int,
        dischargesToday: (json['discharges_today'] ?? 0) as int,
        criticalPatients: (json['critical_patients'] ?? 0) as int,
      );
}
