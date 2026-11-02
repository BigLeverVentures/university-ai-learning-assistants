# A Nested Architecture for University AI Learning Assistants

*Shared foundations, faculty customization, synthetic testing, and improvement through use*

**Article — 2026-11-02**

Christopher Myers, Managing Director, Big Lever Ventures

---

## Executive Summary

Universities can give students useful AI learning support through a shared platform that faculty can adapt and the institution can improve over time. This paper proposes a nested architecture built around four connected elements:

- **Shared foundations.** The university establishes the common teaching approach. Its learning assistant helps students work through confusion, reason for themselves, and develop their own work. That foundation carries into the departmental, subject, and course versions built on it.

- **Faculty customization.** Departmental and subject learning assistants add disciplinary guidance. Course versions inherit both the university foundation and the applicable subject guidance, then add faculty-defined materials and expectations. Local additions stay local. Shared changes flow downward, and the resulting versions are tested before release.

- **Synthetic testing.** Faculty define appropriate instructional behavior, and synthetic students exercise it. Testing begins before launch and recurs throughout the system's life. Evidence from use supplies new questions. Synthetic conversations help reproduce weaknesses, explore related situations, and compare proposed corrections.

- **Improvement through use.** Operational data and voluntary student feedback inform a continuous loop: investigation, testing, approved changes, and measurement after release. Each investigation also adds tests that help protect future versions against recurring problems. Improvements to shared guidance can benefit students in every learning assistant that inherits it.

A companion technical white paper specifies this architecture in detail. It also tests the central idea in a series of exploratory dry runs on a fictional university. A weakness written into shared guidance appeared in both courses that inherited it and in neither of the assistants that did not, and the scoped correction removed it. That result held in a round whose prediction was written down in advance, informed by the earlier rounds, and again on a second test case.

FERPA protections govern student information throughout. Assessment professionals help design measurement from the start, faculty shape instructional behavior, and the university keeps oversight and release authority as more of the improvement process becomes automated. The approach is platform-agnostic: it can use the university's chosen language model and its existing technical and security infrastructure.

## 1. The purpose and organizing architecture

The university brings a shared educational purpose. Departments bring disciplinary knowledge, methods, and scholarly standards. Faculty bring the objectives, materials, and expectations of their courses. An AI instructional platform can follow the same progression, beginning with what the university prescribes and becoming more specific where the context requires.

The overarching goal of the platform is to help students work through confusion, reason for themselves, and develop their own work. The tone is friendly, instructive, and honest about uncertainty. Socratic questions, hints, explanations, examples, and feedback all have a place. The aim is to help students build understanding while they keep responsibility for the work. The design of that guidance matters. In one large study, unguarded access to a general chatbot raised students' practice scores but lowered their later unassisted performance; a version built to give hints instead of answers largely removed that harm.¹

That approach becomes the foundation of the university-wide learning assistant. Once deployed, it offers general learning support, using the university's chosen language model and guided by the university's teaching principles. The university-wide assistant is a useful service in its own right: general assistance in the "voice" of the university. The next tiers make it more specialized for particular kinds of learning.

A subject or departmental tier inherits the university foundation and adds disciplinary methods, terminology, reference materials, and standards of evidence. In history, the learning assistant might help students assess a source, distinguish evidence from interpretation, or work through conflicting accounts. Faculty define what sound guidance looks like in their field.

The course tier brings that assistance into the instructor's classroom as a learning assistant the instructor can modify. Faculty provide learning objectives, assigned readings, assignments, and rules about appropriate help at each stage of the work. The course version incorporates those settings while preserving the university's shared instructional requirements and the applicable departmental guidance.

### Shared changes travel down; local additions stay local

The nested relationship is central to the design. A course-specific instruction applies to that course. It does not change the departmental or university-wide learning assistant. Departmental guidance applies to the learning assistants beneath it, without changing the university foundation or unrelated departments.

Changes to the university foundation, however, carry into the versions that inherit it, and changes to departmental guidance carry into the courses beneath it. The university can maintain shared capabilities where they originate and extend improvements without editing every learning assistant separately. The resulting versions are tested before the changes reach students.

Evidence can travel in the other direction. A course instructor may identify a problem that originates in shared guidance. That finding can inform a proposed university-wide correction, but the course learning assistant does not rewrite its parent. The university evaluates the finding, tests the correction, and approves the shared change.

For this to work, the rules need classes. Some university rules are required, and no course can override them. Preserving student authorship is one. Others are adjustable defaults, which a department or course can tune within set limits. A course's own additions are local. When a course rule would break a requirement, the platform flags the conflict before release and suggests a compliant alternative. For example, a course might ask for "write a model essay for this prompt"; the alternative is a worked example on a parallel topic, or model essays published as course materials.

This gives faculty substantial flexibility within a consistent teaching framework. It also means that a separately trained model is not required for every course. And inheriting guidance never grants access to student records: what a learning assistant inherits is instruction, not data.

## 2. Define teaching, measurement, and responsibility together

The university establishes the common teaching approach and the systems for testing, support, measurement, and student-data protection. Faculty supply the subject and course expertise. Together, those contributions make the platform both broadly useful and adaptable.

University assessment professionals belong in this work from the beginning. Data collection should be designed with them, and they should understand what evidence the system can provide at each level: (1) operational and usage data, (2) user ratings, (3) voluntary feedback on system performance, and (4) detailed problem reports, including conversations students choose to share. Together, assessment and technology professionals can identify the questions that matter, the evidence needed to answer them, and the appropriate means of collecting it.

Assessment, privacy, and technology professionals together connect what is technically possible with what the institution has a valid purpose and authority to collect and analyze. The university defines what information each activity requires, who can access it, and how it is protected and retained. Identifiable usage records and voluntary feedback that the institution maintains can be education records; student choice and privacy protections work together throughout.² Access to student records follows the approved purpose and recipients, independently of which instructional guidance a learning assistant inherits.

Measurement specialists keep responsibility for designing and analyzing academic-impact studies, and technology professionals help make the evidence they need available through approved processes. Adoption and usefulness ratings have value in their own right, but they do not establish gains in academic achievement.

## 3. Test the nested system before and after release

Testing begins with the university-wide learning assistant. Subject and course versions carry those tests forward and add cases for their own materials and expectations. Each assembled assistant is also tested as a whole, so the platform can see how the shared approach and the added guidance work together. A staged rollout might move from the university-wide assistant to subject versions, then to instructor-customized course versions.

Before students use the platform, performance and behavior are tested with synthetic students. Faculty-defined use cases supply the initial questions. Teaching leaders and instructors describe the help students should receive, the situations the learning assistant should handle, and the behavior that would undermine learning goals.

The practical advantage of synthetic testing is experimental control at scale. Conversations can be run in large numbers, repeated under controlled conditions, varied systematically, and extended to edge cases and related failures. When a weakness appears, candidate corrections can be compared, and situations that previously worked well can be re-checked. Because the scenarios are synthetic rather than drawn from student records, these experiments move quickly, without repeated handling of protected student information.

Synthetic students give the system a wide range of interactions to work through: questions, misunderstandings, follow-up exchanges, changes of direction, and attempts to get the learning assistant to supply the answer outright. Faculty define the inquiry and assess the difficult judgments; automated conversations supply the scale and speed needed to explore problems thoroughly.

Failures inform corrections, and corrections go through another round of testing. A clearer instruction may resolve one difficulty while creating another. Faculty assess whether the resulting behavior meets the educational requirements.

The tests need testing too. Simulated learners have well-documented limits, so synthetic tests establish behavior in defined situations, not what real students will do.³ The automated judge that scores conversations must be checked against human judgment before its verdicts are relied on. And a test criterion should be written from the student's side of the exchange, so that it can actually fail when the problem it was written for occurs.

Once the tests are sound, approval is followed by a limited student pilot, which catches usability problems and unexpected interactions before broader release. The tested configuration and its known limits are recorded. Later changes to the model, materials, or platform go through the same checks before going live.

Synthetic student testing continues after launch. Before release, faculty-defined cases supply the questions. Once students use the service, operational evidence and feedback supply new questions for the same process of investigation, correction, and testing.

## 4. Collect useful evidence through the feedback tiers

A useful learning service needs to understand both how the service performs and how students experience it. The feedback structure begins with operational measurement, adds quick student ratings and comments, and offers a path to more detailed troubleshooting. It works at the university, subject, and course levels.

**Start with how the service functions.** Approved operational records can measure access, usage, session frequency, response times, failures, estimated active minutes, and cost. With an approved way to recognize return visits and a defined student population, the university can also measure adoption and repeat use. This supports decisions about access, capacity, reliability, and outreach, without requiring students to submit feedback. Knowing which guidance, materials, and model versions were in use also helps locate a problem when it appears.

**Ask for a quick reaction and invite an explanation.** "Was this helpful?" Students can rate an answer or a session, and flag something that seemed inaccurate. These voluntary responses show perceived usefulness, and they can reveal dissatisfaction even when the service is technically working well. A short follow-up, "What could have worked better?", can help distinguish a confusing explanation from missing material, misleading guidance, or a technical difficulty.

These kinds of feedback are easy to collect and well suited to a largely automated process. A university-approved analysis service can screen them for personal information, group related concerns, and examine the patterns alongside ratings and operational evidence. Staff keep oversight, while automation makes it practical to examine routine feedback at scale. Wider audiences receive findings with student information removed.

**Offer deeper troubleshooting.** If understanding a problem requires more context, invite the student to "Share this chat to help us improve your experience." With explicit consent, students can share a selected conversation for review and approved analysis. They see the records included, the purpose, the recipients, and how long the information will be kept. A relevant paper or attachment is included only through a clear, specific choice. These records can be screened and organized automatically before an authorized reviewer examines what the learning assistant received and how it responded.

Students can give a rating without writing a comment, or describe a problem without sharing a transcript. Participation is voluntary, and declining affects neither grades nor access to the service. Reporting response rates keeps findings in perspective, as does recognizing that students who respond may differ from those who do not.

### Bake FERPA into the feedback design

FERPA can allow access without individual disclosure consent under the school-official exception when its conditions are met, with additional requirements for outsourced providers.⁴ This framework adds an explicit consent process for shared-chat analysis as an additional student choice; it is not a legal requirement for every internal review. When consent is the basis for disclosure, it must identify the records, the purpose, and the recipients, and it must meet FERPA's signature requirements, which qualifying electronic consent can satisfy.⁵ The friendly invitation leads into that process.

Voluntary participation does not remove the protections on identifiable records. Feedback that is easy to collect is not automatically anonymous: a distinctive comment, a small course, or a retained session link can identify a student without a name. A service receiving raw comments must therefore be approved to handle any personal information in them before screening, and the screening itself needs validation. Information counts as de-identified only when the institution has reasonably determined that a student cannot be identified, taking other available information into account. Removing names is a step toward that, not the determination itself.⁶

## 5. Use feedback to drive synthetic investigation and tested corrections

```text
An example: three comments, one possible pattern

History:    "It kept asking me the same question."
Economics:  "I needed an example, but it just told me to think about it again."
Literature: "I said I didn't understand and got another question."
```

A problem confirmed in one course can expose a weakness shared by learning assistants elsewhere in the university. Students might report that their course learning assistant keeps asking questions when they remain confused. Once investigation establishes what produces that behavior, the university can determine which other learning assistants share its cause. Reports from several courses can help reveal a pattern, but one well-understood finding is enough to begin the investigation.

The scope of the problem depends on where it originates. A course-specific instruction may need a local correction. A weakness in departmental guidance may affect the courses that inherit it. A weakness in the university foundation may extend across departments. That set is the problem's blast radius: the learning assistants that share the conditions responsible for the failure, including those whose students have not reported it.

Synthetic students let the university investigate those other learning assistants without waiting for further complaints. Test scenarios can establish whether the same weakness appears, explore related situations, and evaluate a correction across the affected versions. After testing and approval, a shared correction can resolve the problem in other courses, in some cases before their students encounter it. Testing must also establish that the change preserves faculty-defined limits on appropriate help.

This is a practical advantage of the nested architecture: a local finding can lead to a shared correction. The university can improve guidance where the weakness originates and carry the tested improvement into the learning assistants that inherit it.

### Turn the reported problem into a testable scenario

Operational data and student comments may provide enough information to begin testing without reviewing the original conversation. If students report that the learning assistant keeps asking questions when they are confused, a synthetic student can recreate that situation with an invented task.

The investigation then varies the interaction. One synthetic student asks for an explanation; another requests an example; a third tries to obtain a completed assignment. Repeating and changing these conversations shows when the learning assistant gets stuck in questioning, what prompts it to change approach, and whether the change provides appropriate help.

Some problems will need an authorized review of a conversation the student has consented to share. That exchange can help establish the conditions needed to reproduce the failure. The investigation then moves to genuinely synthetic scenarios wherever possible, so experiments can proceed quickly without repeated handling of the original record. Building those scenarios still requires approved handling. The reviewer extracts the conditions that matter, such as the kind of task, the kind of source, and the pattern of confusion, and writes a new scenario with invented content. Changing names in a transcript, or paraphrasing a distinctive exchange, is not the same thing and does not remove its protections.⁶

A candidate correction might direct the learning assistant to offer an explanation or example when questioning stops helping. In a simulated history session about evaluating a source, the response might become:

```text
"Let's try a different approach. A factory owner's account and a worker's
account might describe the same strike differently. Each can tell us
something, but neither gives us everyone's perspective. Whose perspective
is missing from the source you're reading?"
```

The learning assistant supplies an explanation and a separate example, then returns the work to the student.

Synthetic students test that correction across the affected versions, including situations that previously worked well. Faculty define what appropriate help looks like and assess difficult judgments. If the change solves one problem but creates another, for example by supplying too much help with assessed work, the findings inform another correction and another round of testing.

## 6. What a first test showed

The companion white paper puts this example to a test, in a fictional university with two history courses and a mathematics course. History guidance tells the learning assistant to lead with a question about the source, with no point at which it stops asking and helps. The test asked whether that weakness would appear in both history courses, which inherit the guidance, and in neither the university-wide assistant nor the mathematics course, which do not. A commercial language model played the learning assistant, scripted synthetic students played confused learners, and a second model scored the conversations. Four rounds of testing followed, each with its prediction written down before it ran, and each shaped by what the earlier rounds had shown.

**The central idea held.** The history assistants were slow to help a student who kept saying "I don't get it": they asked one or two more questions before explaining. The university-wide and mathematics assistants explained at once. A scoped correction to the history guidance removed the delay, and the separation held again on a test case that had not been used to write the guidance (an earlier round had run it under the old scoring rule). A problem found in one course pointed to a shared cause, and fixing it where it lived fixed it in both courses that inherited it. One prediction, about a partial correction, did not hold.

**The tests improved too.** The first round's scoring rule could not fail. It counted any new question as "changing approach," while the student's complaint was about how long help took. The rule was rewritten from the student's side. The automated judge had not been shown the assignment, and it marked accurate answers as made up until that was corrected. And one early reading of the results turned out to be wrong. The learning assistant followed what a rule's wording said to do, not a numeric setting that contradicted it, so the configuration checker now flags any rule whose wording and setting disagree. A later review of the code found gaps in that checker too, and they have been fixed.

**Instructions are not guarantees.** The guidance that told the assistant to explain sooner worked reliably. But under persistent pressure from a synthetic student, an instruction-only authorship rule gave way in a small share of conversations. Rules that must hold, such as student authorship, need enforcement by the platform as well as instructions to the model. That enforcement is part of the design; these tests did not exercise it.

These were exploratory tests on invented courses, not a deployment, and they say nothing yet about real students or learning. They do show that the architecture's central claim can be tested, and that the process catches its own mistakes.

## 7. Where this work stands

This work proceeds in stages. A series of short articles worked out the argument, and the technical white paper specified the architecture and tested it in the dry runs described above. The next stage is to design a much larger library of synthetic students, with their realism validated against human judgment. That library would span more disciplines and kinds of confusion, with scoring checked against human raters. The model and its deployment would then be refined against it. Implementation with a partner university comes after that: its own model and infrastructure, faculty decisions on the rules, its privacy determinations, and then a limited pilot with real students. Some questions, such as how authorship should apply to an open-topic assignment, belong to faculty at that stage. The white paper states them as tests to run, not as settled answers.

## 8. Conclusion

The nested architecture gives the university a way to turn individual experiences into improvements that benefit students across courses and departments. Its value grows through four connected capabilities:

- **Shared improvements reach more students.** A weakness discovered in one course may originate in guidance inherited by many learning assistants. Once the cause is established, a correction can be tested and applied at the appropriate level, reaching affected courses whose students never reported the problem.

- **Synthetic experimentation turns findings into tested changes.** Operational evidence and student feedback supply questions for investigation. Synthetic students help reproduce weaknesses, vary the conditions, and compare corrections. The same process can test whether a successful explanation or approach would be useful elsewhere.

- **Each investigation strengthens future testing.** Scenarios developed to investigate a problem remain available for later updates, and the tests themselves improve as they are used. Evidence after release shows whether a change is helping and what needs attention next.

- **Automation develops within university oversight.** The platform can organize feedback, identify patterns, propose scenarios and corrections, run synthetic conversations, and compare results. Experience shows which automated findings deserve greater reliance. Faculty shape appropriate instructional behavior, and the university keeps release authority.

FERPA protections govern student information throughout. Assessment professionals help design useful measurement, and claims about academic achievement remain the work of separately designed studies.

What begins as a student's report can become a correction, a lasting test, and better support for students who never submit feedback. Shared foundations make those improvements extensible; recurring testing and evidence from use make continued improvement possible. In that sense the service becomes self-learning, healing, and reinforcing. Each investigation adds to the university's ability to recognize problems, test corrections, and evaluate their effects, and more of that work can be automated over time. The result is a system that learns from use, while faculty shape its teaching approach and the university keeps oversight of its development.

## Notes

1. Hamsa Bastani, Osbert Bastani, Alp Sungu, Haosen Ge, Özge Kabakcı, and Rei Mariman, "Generative AI without guardrails can harm learning: Evidence from high school mathematics," *Proceedings of the National Academy of Sciences* 122, no. 26 (2025): e2422633122. [doi:10.1073/pnas.2422633122](https://doi.org/10.1073/pnas.2422633122)
2. 34 C.F.R. § 99.3, particularly "Education records" and "Personally Identifiable Information." [What definitions apply to these regulations?](https://www.ecfr.gov/current/title-34/subtitle-A/part-99/subpart-A/section-99.3)
3. Alexander Scarlatos, Jaewook Lee, Simon Woodhead, and Andrew Lan, "Simulated Students in Tutoring Dialogues: Substance or Illusion?" *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, July 2026. [ACL Anthology](https://aclanthology.org/2026.acl-long.1960/)
4. 34 C.F.R. § 99.31(a)(1), the school-official exception. [FERPA exceptions](https://www.ecfr.gov/current/title-34/subtitle-A/part-99/subpart-D/section-99.31). See also U.S. Department of Education, [guidance on using online tools and applications](https://studentprivacy.ed.gov/faq/i-want-use-online-tool-or-application-part-my-course-however-i-am-worried-it-violation-ferpa).
5. 34 C.F.R. § 99.30. [Consent requirements](https://www.ecfr.gov/current/title-34/subtitle-A/part-99/subpart-D/section-99.30)
6. 34 C.F.R. § 99.31(b)(1), on de-identified records; and U.S. Department of Education, [What constitutes de-identified records and information?](https://studentprivacy.ed.gov/faq/what-constitutes-de-identified-records-and-information)
