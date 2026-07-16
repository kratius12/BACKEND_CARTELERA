from typing import List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, delete, update
from sqlalchemy.exc import NoResultFound

from app.models.group import Group
from app.models.student_group import StudentGroup
from app.models.student import Student
from app.schemas.groups import GroupCreate, GroupRead, StudentGroupCreate, StudentGroupRead

# -------------------------------------------------
# Service layer for Group management
# -------------------------------------------------

def get_groups(db: Session) -> List[GroupRead]:
    """Retrieve all groups with their assigned students (joined and sorted)."""
    result = db.execute(select(Group).order_by(Group.created_at))
    groups = result.scalars().all()
    group_reads: List[GroupRead] = []
    for grp in groups:
        # fetch student assignments
        stmt = select(StudentGroup).where(StudentGroup.group_id == grp.id)
        assigns = (db.execute(stmt)).scalars().all()
        info_map = {a.student_id: a.info_add for a in assigns}
        
        student_ids = list(info_map.keys())
        if student_ids:
            stud_stmt = select(Student).where(Student.id.in_(student_ids))
            students = (db.execute(stud_stmt)).scalars().all()
            
            # Merge info_add and sort
            for s in students:
                s.group_info = info_map.get(s.id)
            
            def sort_key(s):
                role = (s.group_info or {}).get("role")
                if role == "Encargado": return 0
                if role == "Auxiliar": return 1
                return 2
            students.sort(key=sort_key)
        else:
            students = []

        # build read schema
        grp_read = GroupRead.model_validate(grp)
        grp_read.students = students
        group_reads.append(grp_read)
    return group_reads

def create_group(db: Session, payload: GroupCreate) -> GroupRead:
    """Create a new group and return its representation."""
    stmt = insert(Group).values(name=payload.name).returning(Group)
    result = db.execute(stmt)
    db.commit()
    group = result.scalars().first()
    return GroupRead.model_validate(group)

def add_student_to_group(
    db: Session,
    group_id: UUID,
    payload: StudentGroupCreate,
) -> StudentGroupRead:
    """Assign a student to a group (creates bridge entry)."""
    # Verify group exists
    grp_res = db.execute(select(Group).where(Group.id == group_id))
    grp = grp_res.scalar_one_or_none()
    if not grp:
        raise NoResultFound(f"Group {group_id} not found")
    # Verify student exists
    stu_res = db.execute(select(Student).where(Student.id == payload.student_id))
    stu = stu_res.scalar_one_or_none()
    if not stu:
        raise NoResultFound(f"Student {payload.student_id} not found")
    stmt = insert(StudentGroup).values(
        group_id=group_id,
        student_id=payload.student_id,
        info_add=payload.info_add,
    ).returning(StudentGroup)
    result = db.execute(stmt)
    db.commit()
    bridge = result.scalars().first()
    return StudentGroupRead.model_validate(bridge)

def update_student_role(
    db: Session,
    group_id: UUID,
    student_id: int,
    info_add: dict,
) -> StudentGroupRead:
    """Update the info_add (role) for a student in a group."""
    stmt = update(StudentGroup).where(
        StudentGroup.group_id == group_id,
        StudentGroup.student_id == student_id
    ).values(info_add=info_add).returning(StudentGroup)
    result = db.execute(stmt)
    db.commit()
    bridge = result.scalars().first()
    if not bridge:
        raise NoResultFound("Assignment not found")
    return StudentGroupRead.model_validate(bridge)

def remove_student_from_group(
    db: Session,
    group_id: UUID,
    student_id: int,
) -> None:
    """Delete the bridge row linking a student to a group."""
    stmt = delete(StudentGroup).where(
        StudentGroup.group_id == group_id,
        StudentGroup.student_id == student_id,
    )
    db.execute(stmt)
    db.commit()
